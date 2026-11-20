import { Focusable, GamepadButton, NavEntryPositionPreferences } from "@decky/ui";
import type { FocusableProps, GamepadEvent } from "@decky/ui";
import { useLayoutEffect, useRef, useState } from "react";
import type { ComponentType, ReactNode, Ref, RefAttributes, RefObject } from "react";
import { t } from "../i18n";
import { registerModalFocusScope } from "../lib/modalFocus";
import { adjacentTab } from "../lib/tabNavigation";
import { CompactButton } from "./widgets";
import { useStickyHeader } from "../hooks/useStickyHeader";
import { ControllerButtonHint } from "./ControllerButtonHint";
import { useTabCarouselMotion } from "../hooks/useTabCarouselMotion";
import type { TabMotionView, TabMotionViews } from "../hooks/useTabCarouselMotion";

interface NavigationHandle {
  BFocusWithin: () => boolean;
  TakeFocus: (button?: GamepadButton) => boolean;
}

// Steam supports these navigation props, but Decky's Focusable types omit them.
const NavigationContainer = Focusable as ComponentType<FocusableProps & RefAttributes<HTMLDivElement> & {
  navRef?: Ref<NavigationHandle>;
  focusableIfEmpty?: boolean;
  onMoveLeft?: () => boolean;
  onMoveRight?: () => boolean;
  onMoveDown?: () => boolean;
  scrollIntoViewWhenChildFocused?: boolean | "force";
  fnScrollIntoViewHandler?: (target: { Element?: HTMLElement }) => boolean;
}>;

export interface ArmadaTab {
  id: string;
  title: string;
  icon: ReactNode;
  content: ReactNode;
}

const motionView = (): TabMotionView => ({ shell: null, surface: null, icon: null, label: null });

function TabDecoration({ tab, view }: { tab: ArmadaTab; view: TabMotionView }) {
  return <>
    <span className="armada-tab-surface" ref={(element) => { view.surface = element; }} aria-hidden="true" />
    <span className="armada-tab-title" aria-hidden="true">
      <span className="armada-tab-icon" ref={(element) => { view.icon = element; }}>{tab.icon}</span>
      <span className="armada-tab-label" ref={(element) => { view.label = element; }} title={tab.title}>{tab.title}</span>
    </span>
  </>;
}

export function TabNavigation({ tabs, activeTab, onShowTab, rootRef }: {
  tabs: ArmadaTab[];
  activeTab: string;
  onShowTab: (id: string) => void;
  rootRef?: RefObject<HTMLDivElement | null>;
}) {
  const ownRoot = useRef<HTMLDivElement>(null);
  const root = rootRef || ownRoot;
  const navigation = useRef<NavigationHandle>(null);
  const header = useRef<HTMLDivElement>(null);
  const headerNavigation = useRef<NavigationHandle>(null);
  const panelNavigation = useRef<NavigationHandle>(null);
  const leftEdge = useRef<HTMLSpanElement>(null);
  const rightEdge = useRef<HTMLSpanElement>(null);
  const views = useRef<TabMotionViews>({ previous: motionView(), current: motionView(), next: motionView(), ghost: motionView() });
  const focusContents = useRef(false);
  const [transition, setTransition] = useState<{ from: string; to: string; direction: -1 | 1 } | null>(null);
  const active = tabs.find((tab) => tab.id === activeTab) || tabs[0];
  const previous = adjacentTab(tabs, active.id, -1);
  const next = adjacentTab(tabs, active.id, 1);
  const movement = transition?.to === active.id ? transition : null;
  const leaving = movement && adjacentTab(tabs, movement.from, -movement.direction);
  const enterPanel = () => panelNavigation.current?.TakeFocus(GamepadButton.DIR_DOWN) || false;
  const revealFocus = useStickyHeader(root, header);
  useLayoutEffect(() => {
    if (!root.current) return;
    const scope = registerModalFocusScope(root.current, () => navigation.current?.TakeFocus() || headerNavigation.current?.TakeFocus() || false, () => navigation.current?.BFocusWithin() || false);
    return () => scope.dispose();
  }, [root]);
  useLayoutEffect(() => {
    revealFocus(header.current || undefined);
    if (!focusContents.current) return;
    focusContents.current = false;
    if (!enterPanel()) {
      headerNavigation.current?.TakeFocus(GamepadButton.DIR_DOWN);
    }
  }, [active.id]);
  const prepareMotion = useTabCarouselMotion(header, views, leftEdge, rightEdge, active.id, tabs.map((tab) => tab.title).join("|"));
  const showTab = (direction: -1 | 1, autoFocus = true) => {
    const target = adjacentTab(tabs, active.id, direction);
    if (target.id === active.id) return;
    prepareMotion(direction, target.id);
    setTransition({ from: active.id, to: target.id, direction });
    focusContents.current = autoFocus;
    onShowTab(target.id);
  };
  const handleButton = (event: GamepadEvent) => {
    if (event.defaultPrevented || !root.current?.contains(event.target as Node)) return;
    if (event.detail.button === GamepadButton.BUMPER_LEFT) {
      showTab(-1, !header.current?.contains(event.target as Node));
    } else if (event.detail.button === GamepadButton.BUMPER_RIGHT) {
      showTab(1, !header.current?.contains(event.target as Node));
    } else return;
    event.preventDefault();
    event.stopPropagation();
  };

  return (
    <NavigationContainer
      ref={root}
      navRef={navigation}
      className="armada-control-tabs"
      flow-children="column"
      onButtonDown={handleButton}
      scrollIntoViewWhenChildFocused="force"
      fnScrollIntoViewHandler={(target) => revealFocus(target.Element)}
      actionDescriptionMap={{
        [GamepadButton.BUMPER_LEFT]: previous.title,
        [GamepadButton.BUMPER_RIGHT]: next.title,
      }}
    >
      <NavigationContainer
        ref={header}
        navRef={headerNavigation}
        className="armada-tab-navigation"
        data-direction={movement?.direction}
        role="navigation"
        aria-label={t("navigation.tabs")}
        flow-children="row"
        tabIndex={-1}
        noFocusRing
        onMoveLeft={() => {
          showTab(-1, false);
          return true;
        }}
        onMoveRight={() => {
          showTab(1, false);
          return true;
        }}
        onMoveDown={enterPanel}
        navEntryPreferPosition={NavEntryPositionPreferences.FIRST}
      >
        <span className="armada-tab-boundary" ref={leftEdge}><ControllerButtonHint side="left" /></span>
        <CompactButton
          className="armada-tab-neighbor armada-tab-previous"
          ref={(element) => { views.current.previous.shell = element; }}
          data-tab-id={previous.id}
          aria-label={previous.title}
          focusable={false}
          onClick={() => showTab(-1)}
          onOKActionDescription={previous.title}
        >
          <TabDecoration tab={previous} view={views.current.previous} />
        </CompactButton>
        <div className="armada-tab-current" aria-live="polite" aria-atomic="true">
          <CompactButton
            className="armada-tab-selected"
            ref={(element) => { views.current.current.shell = element; }}
            data-tab-id={active.id}
            aria-label={active.title}
            onClick={enterPanel}
            onOKActionDescription={active.title}
          >
            <TabDecoration tab={active} view={views.current.current} />
          </CompactButton>
        </div>
        <CompactButton
          className="armada-tab-neighbor armada-tab-next"
          ref={(element) => { views.current.next.shell = element; }}
          data-tab-id={next.id}
          aria-label={next.title}
          focusable={false}
          onClick={() => showTab(1)}
          onOKActionDescription={next.title}
        >
          <TabDecoration tab={next} view={views.current.next} />
        </CompactButton>
        <span className="armada-tab-boundary" ref={rightEdge}><ControllerButtonHint side="right" /></span>
        {leaving && <div
          className="armada-tab-ghost"
          ref={(element) => { views.current.ghost.shell = element; }}
          data-tab-id={leaving.id}
          aria-hidden="true"
        ><TabDecoration tab={leaving} view={views.current.ghost} /></div>}
      </NavigationContainer>
      <div className="armada-tab-panels">
          <NavigationContainer
            key={active.id}
            navRef={panelNavigation}
            className="armada-control-tab-content"
            role="tabpanel"
            aria-label={active.title}
            tabIndex={-1}
            focusableIfEmpty
            navEntryPreferPosition={NavEntryPositionPreferences.FIRST}
            noFocusRing
          >
            {active.content}
          </NavigationContainer>
      </div>
    </NavigationContainer>
  );
}
