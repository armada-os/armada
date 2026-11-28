type Mutation = { run: () => void };
const foreground: Mutation[] = [];
const background: Mutation[] = [];
let running = false;

export function runGameSettingsMutation<T>(mutate: () => Promise<T>, priority: "foreground" | "background" = "foreground"): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const queue = priority === "background" ? background : foreground;
    queue.push({ run: () => {
      running = true;
      Promise.resolve().then(mutate).then(resolve, reject).finally(() => {
        running = false;
        drain();
      });
    } });
    drain();
  });
}

function drain(): void {
  if (!running) (foreground.shift() || background.shift())?.run();
}
