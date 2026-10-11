export function cleanOptionalDescription<T extends { description?: string }>(
  values: T,
): T {
  const description = values.description?.trim();
  if (!description) {
    const { description: _omitted, ...rest } = values;
    void _omitted;
    return rest as T;
  }
  return { ...values, description };
}
