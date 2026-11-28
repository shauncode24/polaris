export const CATEGORY_LABELS = {
  technical_depth: 'Technical depth',
  system_design: 'System design',
  behavioral: 'Behavioral',
  role_specific: 'Role specific',
}

export function percent(score) {
  return `${Math.round(score * 100)}%`
}
