import type { AndroidPage } from "../types";

export class AndroidPages {
  pages: string[][] = [];
  index = 0;
  cursors: AndroidPage[] = [];
  private seen = new Set<string>();
  private used = new Set<string>();

  append(ids: string[], cursors: AndroidPage[], consumed?: AndroidPage) {
    const key = (page: AndroidPage) => `${page.kind}:${page.url}`;
    if (consumed) this.used.add(key(consumed));
    const fresh = ids.filter((id) => {
      if (this.seen.has(id)) return false;
      this.seen.add(id);
      return true;
    });
    for (let i = 0; i < fresh.length; i += 20) this.pages.push(fresh.slice(i, i + 20));
    this.cursors = [...new Map([...this.cursors, ...cursors]
      .filter((page) => !this.used.has(key(page)))
      .map((page) => [key(page), page])).values()];
  }

  get ids() { return this.pages[this.index] || []; }
  get canNext() { return this.index + 1 < this.pages.length || this.cursors.length > 0; }
  next() {
    if (this.index + 1 >= this.pages.length) return false;
    this.index++;
    return true;
  }
  previous() { this.index = Math.max(0, this.index - 1); }
}
