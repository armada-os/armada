export interface RouteRenderPatchHandle {
  hasUnpatched?: boolean;
  unpatch(): void;
}

export type RouteRenderPatchReleaseError = (key: string, error: unknown) => void;

/**
 * Decky rebuilds its route-child wrapper on router renders. Keep only the
 * handle attached to the current wrapper instead of retaining every obsolete
 * wrapper until plugin dismount.
 */
export class RouteRenderPatchRegistry {
  private readonly handles = new Map<string, RouteRenderPatchHandle>();

  get size(): number {
    return this.handles.size;
  }

  replace(
    key: string,
    next: RouteRenderPatchHandle,
    onError?: RouteRenderPatchReleaseError,
  ): void {
    if (this.handles.get(key) === next) return;
    this.release(key, onError);
    this.handles.set(key, next);
  }

  release(key: string, onError?: RouteRenderPatchReleaseError): void {
    const current = this.handles.get(key);
    if (!current) return;
    this.handles.delete(key);
    if (current.hasUnpatched) return;
    try {
      current.unpatch();
    } catch (error) {
      onError?.(key, error);
    }
  }

  releaseAll(onError?: RouteRenderPatchReleaseError): void {
    Array.from(this.handles.keys()).forEach((key) => this.release(key, onError));
  }
}
