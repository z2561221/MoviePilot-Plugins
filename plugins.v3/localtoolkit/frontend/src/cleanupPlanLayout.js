export const PLAN_ROW_HEIGHT = 36
export const PLAN_HEADER_HEIGHT = 32
export const PLAN_MOBILE_ROW_HEIGHT = 60

/** 按列表实际可用高度分页，不用滚动条容纳一页中放不下的条目。 */
export function fitPlanPage(height, mobile, page = 1, previousSize = 15) {
  const available = Number.isFinite(height) ? Math.max(0, height) : 0
  const rowHeight = mobile ? PLAN_MOBILE_ROW_HEIGHT : PLAN_ROW_HEIGHT
  const headerHeight = mobile ? 0 : PLAN_HEADER_HEIGHT
  const pageSize = Math.max(1, Math.min(15, Math.floor((available - headerHeight) / rowHeight)))
  const firstIndex = Math.max(0, page - 1) * previousSize
  return { pageSize, page: Math.floor(firstIndex / pageSize) + 1 }
}
