#include <bit>
#include <cstdint>

#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

// Test the production samplers without exporting them from Gamescope.
#include "color_helpers.cpp"
#include <armada-autohdr.h>

static armada_autohdr_transform test_transform( const glm::mat3 &matrix, float sdrNits, float targetNits )
{
	armada_autohdr_transform transform{ {}, sdrNits, targetNits };
	for ( int column = 0; column < 3; column++ )
		for ( int row = 0; row < 3; row++ )
			transform.native_from_output[column * 3 + row] = matrix[column][row];
	return transform;
}

static glm::vec3 apply_transform( glm::vec3 color, const armada_autohdr_transform &transform )
{
	const auto mapped = armada_autohdr_apply_transform( &transform, { color.r, color.g, color.b } );
	return { mapped.r, mapped.g, mapped.b };
}

static constexpr displaycolorimetry_t kNativeP3{
	.primaries = { { 0.68f, 0.32f }, { 0.265f, 0.69f }, { 0.15f, 0.06f } },
	.white = displaycolorimetry_709.white,
};

static void require_finite( float value )
{
	// Check the bits because fast-math can remove std::isfinite checks.
	REQUIRE( ( std::bit_cast<uint32_t>( value ) & 0x7f800000u ) != 0x7f800000u );
}

struct AutoHdrTestLuts
{
	lut1d_t shaper;
	lut3d_t color;
	displaycolorimetry_t output;
	glm::mat3 nativeFromOutput;
	EOTF eotf;
	float peak;

	glm::vec3 decode( glm::vec3 encoded ) const
	{
		return eotf == EOTF_PQ ? pq_to_nits( encoded )
			: glm::pow( encoded, glm::vec3( 2.2f ) ) * peak;
	}

	glm::vec3 sample( glm::vec3 input ) const
	{
		return decode( ApplyLut3D_Tetrahedral( color, ApplyLut1D_Linear( shaper, input ) ) );
	}
};

static AutoHdrTestLuts build_luts( const displaycolorimetry_t &display, EOTF eotf,
	float peak, float gain = 1.0f, bool autoHdr = true )
{
	AutoHdrTestLuts luts{ .output = eotf == EOTF_PQ ? displaycolorimetry_2020 : display,
		.eotf = eotf, .peak = peak };
	displaycolorimetry_t input{};
	colormapping_t mapping{};
	buildSDRColorimetry( &input, &mapping, -1.0f, display );
	luts.nativeFromOutput = display == luts.output ? glm::mat3( 1.0f ) :
		glm::inverse( normalised_primary_matrix( display.primaries, display.white, 1.0f ) ) *
			normalised_primary_matrix( luts.output.primaries, luts.output.white, 1.0f );
	const auto transform = test_transform( luts.nativeFromOutput, 100.0f, peak );
	tonemapping_t tonemapping{};
	tonemapping.g22_luminance = peak;
	if ( autoHdr )
	{
		tonemapping.preGainTransform = []( glm::vec3 color, const void *data ) {
			return apply_transform( color, *static_cast<const armada_autohdr_transform *>( data ) );
		};
		tonemapping.preGainTransformData = &transform;
	}
	calcColorTransform<rendervulkan::s_nLutEdgeSize3d>( &luts.shaper, rendervulkan::s_nLutSize1d,
		&luts.color, input, EOTF_Gamma22, luts.output, eotf, display, {},
		k_EChromaticAdapatationMethod_Bradford, mapping, {}, tonemapping, nullptr, gain );
	for ( auto *channel : { &luts.shaper.dataR, &luts.shaper.dataG, &luts.shaper.dataB } )
		for ( float &value : *channel )
		{
			require_finite( value );
			value = quantize_lut_value_16bit( value ) / 65535.0f;
		}
	for ( glm::vec3 &color : luts.color.data )
		for ( int channel = 0; channel < 3; ++channel )
		{
			require_finite( color[channel] );
			REQUIRE( color[channel] >= 0.0f );
			REQUIRE( color[channel] <= 1.0f );
			color[channel] = quantize_lut_value_16bit( color[channel] ) / 65535.0f;
		}
	return luts;
}

TEST_CASE( "Auto HDR LUTs stay finite and respect the output peak", "[auto_hdr]" )
{
	for ( const auto &display : { displaycolorimetry_709, kNativeP3 } )
		for ( const EOTF eotf : { EOTF_Gamma22, EOTF_PQ } )
			for ( const float peak : { 100.0f, 500.0f, 1000.0f } )
			{
				CAPTURE( eotf, peak );
				const auto luts = build_luts( display, eotf, peak );
				for ( const glm::vec3 &encoded : luts.color.data )
				{
					const glm::vec3 native = luts.nativeFromOutput * luts.decode( encoded );
					for ( const float value : { native.r, native.g, native.b } )
					{
						require_finite( value );
						REQUIRE( value <= peak * 1.001f );
					}
				}
				REQUIRE( luts.sample( glm::vec3( 0.0f ) ) == glm::vec3( 0.0f ) );
			}
}

TEST_CASE( "Auto HDR preserves SDR chromaticity through the shared LUT path", "[auto_hdr]" )
{
	for ( const auto &display : { displaycolorimetry_709, kNativeP3 } )
		for ( const EOTF eotf : { EOTF_Gamma22, EOTF_PQ } )
			for ( const float gain : { 1.0f / 3.0f, 0.5f, 1.0f } )
			{
				const auto luts = build_luts( display, eotf, 700.0f, gain );
				const auto sdr = build_luts( display, eotf, 700.0f, gain, false );
				const glm::mat3 xyzFromOutput = normalised_primary_matrix( luts.output.primaries, luts.output.white, 1.0f );
				for ( const auto &input : { glm::vec3( 0.25f, 0.1f, 0.05f ), glm::vec3( 1.0f, 0.01f, 0.01f ),
					glm::vec3( 0.9f, 0.45f, 0.1f ), glm::vec3( 0.05f, 0.1f, 0.8f ), glm::vec3( 0.5f ) } )
				{
					CAPTURE( display.primaries.r.x, eotf, gain, input.r, input.g, input.b );
					const glm::vec3 source = xyzFromOutput * sdr.sample( input );
					const glm::vec3 mapped = xyzFromOutput * luts.sample( input );
					const glm::vec2 sourceXY = glm::vec2( source ) / ( source.x + source.y + source.z );
					const glm::vec2 mappedXY = glm::vec2( mapped ) / ( mapped.x + mapped.y + mapped.z );
					REQUIRE( glm::distance( sourceXY, mappedXY ) < 0.003f );
				}
			}
}

TEST_CASE( "Auto HDR applies HDR output gain after tone mapping", "[auto_hdr]" )
{
	for ( const EOTF eotf : { EOTF_Gamma22, EOTF_PQ } )
	{
		const float peak = 700.0f;
		float previousMidtone = -1.0f;
		for ( const float gain : { 0.0f, 1.0f / 3.0f, 0.5f, 1.0f } )
		{
			CAPTURE( eotf, gain );
			const auto luts = build_luts( kNativeP3, eotf, peak, gain );
			const glm::vec3 white = luts.sample( glm::vec3( 1.0f ) );
			if ( gain == 0.0f )
				REQUIRE( white == glm::vec3( 0.0f ) );
			else
			{
				REQUIRE( white.r > 0.0f );
				REQUIRE( white.r <= peak * 1.001f );
			}
			if ( gain == 1.0f && eotf == EOTF_Gamma22 )
				REQUIRE( white.r == Catch::Approx( peak ) );
			const float midtone = luts.sample( glm::vec3( 0.5f ) ).r;
			REQUIRE( midtone > previousMidtone );
			previousMidtone = midtone;
		}
	}
}
