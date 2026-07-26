import assert from "node:assert/strict";
import test from "node:test";
import {
  ARMADA_AUTO_HDR_QAM_MARKER,
  PERFORMANCE_QAM_TITLE_TOKEN,
  canDescendPerformanceComponent,
  claimPerformanceHdrProbeOwner,
  evictOldestPerformanceHdrInjection,
  findUniqueQamMenuElement,
  findUniqueQamTabsArray,
  injectPerformanceHdrControls,
  injectPerformanceHdrPanel,
  isReactClassComponent,
  restorePerformanceHdrPanel,
  releasePerformanceHdrProbeOwner,
  wrapPerformanceComponents,
} from "../src/lib/performanceHdrInjection.ts";

const PERFORMANCE_KEY = 5;
const descriptor = (key, locId, panel) => ({ key, title: { props: { locId } }, panel });
const performance = (panel = { type: "NativePerformancePanel" }) =>
  descriptor(PERFORMANCE_KEY, PERFORMANCE_QAM_TITLE_TOKEN, panel);
const wrapper = (nativePanel) => ({
  type: "ArmadaPerformancePanel",
  props: { nativePanel, [ARMADA_AUTO_HDR_QAM_MARKER]: "panel" },
});

test("wraps only the exact unique Performance descriptor and preserves its panel", () => {
  const original = performance();
  const tabs = [descriptor(4, "#QuickAccess_Tab_Settings_Title", {}), original];
  const result = injectPerformanceHdrPanel(tabs, PERFORMANCE_KEY, wrapper);
  assert.equal(result.status, "injected");
  assert.notEqual(result.tabs, tabs);
  assert.equal(result.tabs[0], tabs[0]);
  assert.equal(result.tabs[1].panel.props.nativePanel, original.panel);
});

test("fails closed for ambiguous or approximate Performance fingerprints", () => {
  const duplicate = [performance(), performance()];
  assert.equal(injectPerformanceHdrPanel(duplicate, PERFORMANCE_KEY, wrapper).status, "fingerprint-mismatch");
  const approximate = [descriptor(PERFORMANCE_KEY, "#Wrong_Title", {})];
  assert.equal(injectPerformanceHdrPanel(approximate, PERFORMANCE_KEY, wrapper).status, "fingerprint-mismatch");
});

test("injection is idempotent and reversible", () => {
  const once = injectPerformanceHdrPanel([performance()], PERFORMANCE_KEY, wrapper);
  const twice = injectPerformanceHdrPanel(once.tabs, PERFORMANCE_KEY, wrapper);
  assert.equal(twice.status, "already-injected");
  assert.deepEqual(twice.injection, once.injection);
  const restored = restorePerformanceHdrPanel(twice.tabs, PERFORMANCE_KEY, twice.injection);
  assert.equal(restored.status, "restored");
  assert.equal(restored.tabs[0].panel, once.injection.originalPanel);
});

test("restore never overwrites a panel replaced after injection", () => {
  const injected = injectPerformanceHdrPanel([performance()], PERFORMANCE_KEY, wrapper);
  const replacement = { type: "SteamReplacementPanel" };
  const changed = [{ ...injected.tabs[0], panel: replacement }];
  const restored = restorePerformanceHdrPanel(changed, PERFORMANCE_KEY, injected.injection);
  assert.equal(restored.status, "not-owned");
  assert.equal(restored.tabs, changed);
});

test("bounded tracking restores the owned oldest panel before eviction", () => {
  const oldest = injectPerformanceHdrPanel([performance()], PERFORMANCE_KEY, wrapper);
  const newer = injectPerformanceHdrPanel([performance()], PERFORMANCE_KEY, wrapper);
  const tracked = new Map([
    [oldest.tabs, oldest.injection],
    [newer.tabs, newer.injection],
  ]);
  const result = evictOldestPerformanceHdrInjection(tracked, PERFORMANCE_KEY);
  assert.equal(result.status, "restored");
  assert.equal(oldest.tabs[0].panel, oldest.injection.originalPanel);
  assert.equal(tracked.has(oldest.tabs), false);
  assert.equal(tracked.has(newer.tabs), true);
});

test("eviction contains a no-longer-owned panel and still forgets it", () => {
  const injected = injectPerformanceHdrPanel([performance()], PERFORMANCE_KEY, wrapper);
  injected.tabs[0] = { ...injected.tabs[0], panel: { type: "SteamReplacement" } };
  const tracked = new Map([[injected.tabs, injected.injection]]);
  const result = evictOldestPerformanceHdrInjection(tracked, PERFORMANCE_KEY);
  assert.equal(result.status, "not-owned");
  assert.equal(tracked.size, 0);
});

test("finds Browser QAM through a React portal subtree", () => {
  const tabs = [performance()];
  const output = { type: "Tabs", props: { tabs } };
  const menu = {
    type: () => output,
    props: { onFocusNavActivated() {}, onFocusNavDeactivated() {} },
  };
  const tree = { type: "Browser", props: { children: { children: menu } } };
  assert.equal(findUniqueQamMenuElement(tree), menu);
  assert.equal(findUniqueQamTabsArray(output), tabs);
});

test("menu traversal fails closed when the QAM fingerprint is ambiguous", () => {
  const menu = () => ({
    type: "Menu",
    props: { onFocusNavActivated() {}, onFocusNavDeactivated() {} },
  });
  assert.equal(findUniqueQamMenuElement({ children: [menu(), menu()] }), undefined);
});

function NativePerformanceProfile() {
  return "steamos_platform_performance_profile #PlatformPerformanceProfile_Label";
}

function NativeAdvancedView() {
  return "#Common_Advanced_View";
}

function NativeAllowTearing() {
  return "gamescope_allow_tearing #QuickAccess_Tab_Perf_EnableTearing";
}

function OtherControl() {
  return null;
}

const element = (type, props = {}) => ({ type, props });
const marker = (kind) => element(OtherControl, { [ARMADA_AUTO_HDR_QAM_MARKER]: kind });

function nativePerformanceTree() {
  const tearing = element(NativeAllowTearing);
  const advanced = element(NativeAdvancedView, {
    children: [element(OtherControl), tearing, element(OtherControl)],
  });
  const profile = element(NativePerformanceProfile);
  return {
    tree: element(OtherControl, {
      children: [element(OtherControl), profile, advanced, element(OtherControl)],
    }),
    tearing,
    profile,
    advanced,
  };
}

test("places the toggle after Allow Tearing without changing Performance Profile", () => {
  const native = nativePerformanceTree();
  const toggle = marker("toggle");
  const result = injectPerformanceHdrControls(native.tree, toggle);

  assert.equal(result.status, "injected");
  assert.notEqual(result.tree, native.tree);
  assert.equal(result.tree.props.children[1], native.profile);
  const nextAdvanced = result.tree.props.children[2];
  assert.deepEqual(nextAdvanced.props.children.slice(1, 3), [native.tearing, toggle]);
  assert.deepEqual(native.advanced.props.children, [
    native.advanced.props.children[0],
    native.tearing,
    native.advanced.props.children[2],
  ]);
});

test("places the toggle after a unique anchor held by a split parent array", () => {
  const profile = element(NativePerformanceProfile);
  const tearing = element(NativeAllowTearing);
  const profileParent = element(OtherControl, {
    children: [element(OtherControl), profile],
  });
  const tearingParent = element(OtherControl, {
    children: [tearing, element(OtherControl)],
  });
  const advancedParent = element(NativeAdvancedView, {
    children: [tearingParent],
  });
  const tree = element(OtherControl, {
    children: [profileParent, advancedParent],
  });
  const toggleControl = marker("toggle");
  const result = injectPerformanceHdrControls(tree, toggleControl);

  assert.equal(result.status, "injected");
  assert.equal(result.tree.props.children[0], profileParent);
  assert.deepEqual(result.tree.props.children[1].props.children[0].props.children, [
    tearing,
    toggleControl,
    tearingParent.props.children[1],
  ]);
});

test("lifts the toggle beside a scalar owner wrapper without nesting its row", () => {
  const profile = element(NativePerformanceProfile);
  const tearing = element(NativeAllowTearing);
  const profileParent = element(OtherControl, { children: profile });
  const tearingParent = element(OtherControl, { children: tearing });
  const advancedParent = element(NativeAdvancedView, { children: tearingParent });
  const tree = element(OtherControl, {
    children: [profileParent, advancedParent],
  });
  const toggleControl = marker("toggle");
  const result = injectPerformanceHdrControls(tree, toggleControl);

  assert.equal(result.status, "injected");
  assert.deepEqual(result.tree.props.children, [
    profileParent,
    {
      ...advancedParent,
      props: {
        ...advancedParent.props,
        children: [tearingParent, toggleControl],
      },
    },
  ]);
  assert.equal(profileParent.props.children, profile);
  assert.equal(tearingParent.props.children, tearing);
});

test("scalar insertion fails closed when an anchor has multiple direct parents", () => {
  const profile = element(NativePerformanceProfile);
  const tearing = element(NativeAllowTearing);
  const advanced = element(NativeAdvancedView);
  const tree = element(OtherControl, {
    children: [
      element(OtherControl, { children: profile }),
      element(OtherControl, { children: advanced }),
      element(OtherControl, { children: tearing }),
      element(OtherControl, { children: tearing }),
    ],
  });
  const result = injectPerformanceHdrControls(
    tree,
    marker("toggle"),
  );

  assert.equal(result.status, "fingerprint-mismatch");
  assert.equal(result.tree, tree);
});

test("insertion fails closed when one parent repeats the same anchor object", () => {
  const profile = element(NativePerformanceProfile);
  const tearing = element(NativeAllowTearing);
  const advanced = element(NativeAdvancedView);
  const tree = element(OtherControl, {
    children: [
      element(OtherControl, { children: profile }),
      element(OtherControl, { children: advanced }),
      element(OtherControl, { children: [tearing, tearing] }),
    ],
  });
  const result = injectPerformanceHdrControls(
    tree,
    marker("toggle"),
  );

  assert.equal(result.status, "fingerprint-mismatch");
  assert.equal(result.tree, tree);
});

test("bounded descent wraps every shallow component and not nested descendants", () => {
  function Dispatcher() {
    return null;
  }
  function DeeperA() {
    return null;
  }
  function DeeperB() {
    return null;
  }
  const dispatcher = element(Dispatcher, {
    children: [element(DeeperA), element(DeeperB)],
  });
  const tree = element("fragment", { children: dispatcher });
  const wrapped = { type: "Probe", props: { nativePanel: dispatcher } };
  const result = wrapPerformanceComponents(tree, (candidate) => {
    assert.equal(candidate, dispatcher);
    return wrapped;
  });

  assert.equal(result.status, "wrapped");
  assert.equal(result.count, 1);
  assert.equal(result.tree.props.children, wrapped);
  const multiple = wrapPerformanceComponents(
    element("fragment", { children: [element(DeeperA), element(DeeperB)] }),
    (candidate, index) => ({ type: "Probe", props: { candidate, index } }),
  );
  assert.equal(multiple.status, "wrapped");
  assert.equal(multiple.count, 2);
  assert.deepEqual(
    multiple.tree.props.children.map((child) => child.props.candidate.type),
    [DeeperA, DeeperB],
  );
});

test("bounded descent stops at the configured depth and rejects invalid depths", () => {
  assert.equal(canDescendPerformanceComponent(3, 4), true);
  assert.equal(canDescendPerformanceComponent(4, 4), false);
  assert.equal(canDescendPerformanceComponent(-1, 4), false);
  assert.equal(canDescendPerformanceComponent(1.5, 4), false);
});

test("bounded descent fails closed when shallow component fanout is ambiguous", () => {
  const branches = Array.from({ length: 33 }, (_, index) => {
    const Branch = function Branch() {
      return index;
    };
    return element(Branch);
  });
  const tree = element("fragment", { children: branches });
  const result = wrapPerformanceComponents(tree, (candidate) => ({
    type: "Probe",
    props: { candidate },
  }));
  assert.equal(result.status, "fingerprint-mismatch");
  assert.equal(result.tree, tree);
});

test("bounded descent never invokes React class components as plain functions", () => {
  class ClassBranch {
    render() {
      return null;
    }
  }
  ClassBranch.prototype.isReactComponent = {};
  function FunctionBranch() {
    return null;
  }
  const classElement = element(ClassBranch);
  const functionElement = element(FunctionBranch);
  const mixedTree = element("fragment", {
    children: [classElement, functionElement],
  });
  const mixed = wrapPerformanceComponents(mixedTree, (candidate) => ({
    type: "Probe",
    props: { candidate },
  }));
  assert.equal(isReactClassComponent(ClassBranch), true);
  assert.equal(isReactClassComponent(FunctionBranch), false);
  assert.equal(mixed.status, "wrapped");
  assert.equal(mixed.count, 1);
  assert.equal(mixed.tree.props.children[0], classElement);
  assert.equal(mixed.tree.props.children[1].props.candidate, functionElement);

  const classOnly = wrapPerformanceComponents(
    element("fragment", { children: [classElement] }),
    () => {
      throw new Error("class component must not be wrapped");
    },
  );
  assert.equal(classOnly.status, "fingerprint-mismatch");
});

test("placement rejects unrelated Advanced and Allow Tearing branches", () => {
  const tree = element(OtherControl, {
    children: [
      element(NativePerformanceProfile),
      element(NativeAdvancedView),
      element(OtherControl, { children: element(NativeAllowTearing) }),
    ],
  });
  const result = injectPerformanceHdrControls(tree, marker("toggle"));
  assert.equal(result.status, "fingerprint-mismatch");
  assert.equal(result.tree, tree);
});

test("places the toggle when Steam does not expose Performance Profile", () => {
  const tearing = element(NativeAllowTearing);
  const advanced = element(NativeAdvancedView, {
    children: [element(OtherControl), tearing],
  });
  const tree = element(OtherControl, {
    children: [advanced, element(OtherControl)],
  });
  const toggle = marker("toggle");
  const result = injectPerformanceHdrControls(tree, toggle);

  assert.equal(result.status, "injected");
  assert.deepEqual(
    result.tree.props.children[0].props.children,
    [advanced.props.children[0], tearing, toggle],
  );
});

test("probe ownership releases only when the claimed insertion owner unmounts", () => {
  const session = {};
  const first = {};
  const second = {};
  assert.equal(claimPerformanceHdrProbeOwner(session, first), true);
  assert.equal(claimPerformanceHdrProbeOwner(session, second), false);
  releasePerformanceHdrProbeOwner(session, second);
  assert.equal(session.owner, first);
  releasePerformanceHdrProbeOwner(session, first);
  assert.equal(session.owner, undefined);
  assert.equal(claimPerformanceHdrProbeOwner(session, second), true);
  assert.equal(session.owner, second);
});

test("placement rejects duplicate semantic siblings", () => {
  const tree = element(OtherControl, {
    children: [
      element(NativePerformanceProfile),
      element(NativeAdvancedView, {
        children: [
          element(NativeAllowTearing),
          element(NativeAllowTearing),
        ],
      }),
    ],
  });
  const result = injectPerformanceHdrControls(tree, marker("toggle"));
  assert.equal(result.status, "fingerprint-mismatch");
  assert.equal(result.tree, tree);
});

test("inner placement is idempotent and fails closed on ambiguous anchors", () => {
  const native = nativePerformanceTree();
  const once = injectPerformanceHdrControls(native.tree, marker("toggle"));
  assert.equal(
    injectPerformanceHdrControls(once.tree, marker("toggle")).status,
    "already-injected",
  );

  const duplicateTearing = element(OtherControl, {
    children: [
      native.profile,
      element(NativeAdvancedView, {
        children: [element(NativeAllowTearing), element(NativeAllowTearing)],
      }),
    ],
  });
  const ambiguous = injectPerformanceHdrControls(
    duplicateTearing,
    marker("toggle"),
  );
  assert.equal(ambiguous.status, "fingerprint-mismatch");
  assert.equal(ambiguous.tree, duplicateTearing);
});
