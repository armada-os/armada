export interface Element {
  type: string | ((props: any) => any);
  props: any;
  key?: string;
  rendered?: any;
}

export function elements(tree: any): Element[] {
  if (Array.isArray(tree)) return tree.flatMap(elements);
  if (!tree || typeof tree !== "object") return [];
  // Expanded fixtures inspect the rendered output, not the original child props.
  const children = Object.prototype.hasOwnProperty.call(tree, "rendered") ? tree.rendered : tree.props?.children;
  return [tree, ...elements(children)];
}
