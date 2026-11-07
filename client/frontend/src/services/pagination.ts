export const PAGE_SIZE = 100;

/** Busca todas as páginas de uma listagem paginada por skip/limit. */
export async function fetchAllPages<T>(
  fetchPage: (skip: number, limit: number) => Promise<T[]>,
): Promise<T[]> {
  const items: T[] = [];
  for (let skip = 0; ; skip += PAGE_SIZE) {
    const page = await fetchPage(skip, PAGE_SIZE);
    items.push(...page);
    if (page.length < PAGE_SIZE) return items;
  }
}
