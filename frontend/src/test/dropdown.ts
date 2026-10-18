import { nextTick } from 'vue'

export async function openDropdown(control: Element | null | undefined) {
  if (!control) throw new Error('Dropdown control not found')
  const trigger = (
    control.matches('button[aria-haspopup="listbox"]')
      ? control
      : control.querySelector('button[aria-haspopup="listbox"]')
  ) as HTMLButtonElement | null
  if (!trigger) throw new Error('Dropdown trigger not found')
  if (trigger.getAttribute('aria-expanded') !== 'true') trigger.click()
  await nextTick()
  await nextTick()
  return Array.from(
    document
      .getElementById(trigger.getAttribute('aria-controls')!)
      ?.querySelectorAll<HTMLButtonElement>('[role=option]') || [],
  )
}

export async function chooseDropdown(control: Element | null | undefined, value: string) {
  const options = await openDropdown(control)
  const option = options.find((option) => option.value === value)
  if (!option || option.disabled) throw new Error(`Dropdown option unavailable: ${value}`)
  option.click()
  await nextTick()
  await nextTick()
}
