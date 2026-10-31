// Some protocol dependencies log whole Signal sessions through console.warn.
// This is a dedicated process: only our explicit, allowlisted status logger may
// write diagnostics. Apply before dynamically importing the protocol library.
export function suppressDependencyConsole(target = console) {
  for (const method of ['log', 'info', 'warn', 'error', 'debug', 'trace', 'dir', 'table', 'assert']) target[method] = () => {};
}
