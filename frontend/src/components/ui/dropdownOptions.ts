import { Fragment, isVNode, type VNode } from 'vue'

export type DropdownValue = string | number | boolean | null | undefined
export interface DropdownOption<T = DropdownValue> {
  value: T
  label: string
  disabled?: boolean
  icon?: string
  description?: string
  triggerLabel?: string
}

function text(children: unknown): string {
  if (typeof children === 'string' || typeof children === 'number') return String(children)
  if (Array.isArray(children)) return children.map(text).join('')
  if (isVNode(children)) return text(children.children)
  return ''
}

// Read declarative options without mounting a native select/picker. Values keep
// their original types, including false, zero and null; fragments support v-for.
export function slotOptions(nodes: VNode[], group = '', disabled = false): DropdownOption[] {
  return nodes.flatMap((node) => {
    if (node.type === Fragment || node.type === 'optgroup') {
      return slotOptions(
        (node.children || []) as VNode[],
        node.props?.label || group,
        disabled || (node.props?.disabled !== undefined && node.props.disabled !== false),
      )
    }
    if (node.type !== 'option') return []
    const label = node.props?.label ?? text(node.children).trim()
    return [
      {
        value: node.props && 'value' in node.props ? node.props.value : label,
        label,
        disabled: disabled || (node.props?.disabled !== undefined && node.props.disabled !== false),
        description: group || undefined,
      },
    ]
  })
}
