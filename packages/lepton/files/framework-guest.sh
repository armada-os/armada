#!/system/bin/sh
# Runs inside a Lepton container for armada-lepton-tool.
# compile is adapted from SteamOS-ARM-Handhelds' compile-odex.sh (GPL-2.0, hashtagbasit).
set -e
T=/data/local/tmp/armada
cd "$T"

# podman exec carries none of init's environment, and ART needs it.
while read -r kw name value; do
    [ "$kw" = export ] && export "$name=$value"
done </init.environ.rc
VM=/apex/com.android.art/bin/dalvikvm64

case "$1" in
disassemble)
    rm -rf dex smali && mkdir dex
    unzip -o -q /system/framework/services.jar classes.dex -d dex
    $VM -Xmx512m -cp baksmali.dex.jar org.jf.baksmali.Main d -a 30 dex/classes.dex -o smali
    ;;
assemble)
    rm -f classes.new.dex
    $VM -Xmx512m -cp smali.dex.jar org.jf.smali.Main a -a 30 smali -o classes.new.dex
    ;;
compile)
    # Everything that embeds services.jar's checksum: its own oat files,
    # ethernet-service's, and the two system_server apex jars Valve prebakes
    # into /data/dalvik-cache.
    BCP=$DEX2OATBOOTCLASSPATH
    d2o() {
        filter=$1; shift
        /apex/com.android.art/bin/dex2oat64 --instruction-set=arm64 --instruction-set-variant=cortex-a76 \
            --instruction-set-features=default --compiler-filter="$filter" \
            --boot-image=/apex/com.android.art/javalib/boot.art:/system/framework/boot-framework.art \
            --runtime-arg -Xbootclasspath:"$BCP" --runtime-arg -Xbootclasspath-locations:"$BCP" \
            --runtime-arg -Xms64m --runtime-arg -Xmx512m --generate-mini-debug-info -j4 "$@"
    }
    B=/system/framework/org.lineageos.platform.jar:/system/framework/com.android.location.provider.jar
    E=/system/framework/ethernet-service.jar
    SP=/apex/com.android.permission/javalib/service-permission.jar
    IK=/apex/com.android.ipsec/javalib/android.net.ipsec.ike.jar
    O=$T/out/system/framework/oat/arm64
    DC=$T/out/data/dalvik-cache/arm64
    rm -rf out && mkdir -p "$O" "$DC"

    d2o speed --compilation-reason=prebuilt --dex-file=$T/services.jar --dex-location=/system/framework/services.jar \
        --oat-file=$O/services.odex --output-vdex=$O/services.vdex --app-image-file=$O/services.art --image-format=lz4 \
        --oat-location=/system/framework/oat/arm64/services.odex --class-loader-context="PCL[$B]"
    d2o speed --compilation-reason=prebuilt --dex-file=$E --dex-location=$E \
        --oat-file=$O/ethernet-service.odex --output-vdex=$O/ethernet-service.vdex \
        --oat-location=/system/framework/oat/arm64/ethernet-service.odex \
        --class-loader-context="PCL[$B:$T/services.jar]" --stored-class-loader-context="PCL[$B:/system/framework/services.jar]"
    d2o verify --dex-file=$SP --dex-location=$SP \
        --oat-file=$DC/apex@com.android.permission@javalib@service-permission.jar@classes.dex \
        --output-vdex=$DC/apex@com.android.permission@javalib@service-permission.jar@classes.vdex \
        --oat-location=/data/dalvik-cache/arm64/apex@com.android.permission@javalib@service-permission.jar@classes.dex \
        --class-loader-context="PCL[$B:$T/services.jar:$E]" --stored-class-loader-context="PCL[$B:/system/framework/services.jar:$E]"
    d2o verify --dex-file=$IK --dex-location=$IK \
        --oat-file=$DC/apex@com.android.ipsec@javalib@android.net.ipsec.ike.jar@classes.dex \
        --output-vdex=$DC/apex@com.android.ipsec@javalib@android.net.ipsec.ike.jar@classes.vdex \
        --oat-location=/data/dalvik-cache/arm64/apex@com.android.ipsec@javalib@android.net.ipsec.ike.jar@classes.dex \
        --class-loader-context="PCL[$B:$T/services.jar:$E:$SP]" --stored-class-loader-context="PCL[$B:/system/framework/services.jar:$E:$SP]"
    ;;
*)
    echo "usage: framework-guest.sh disassemble|assemble|compile" >&2
    exit 2
    ;;
esac
