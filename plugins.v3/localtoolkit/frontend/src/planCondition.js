/** 返回清理计划快照中的观看与收藏条件，未知值保持可辨认。 */
export function planConditionSummary(item = {}) {
  const played = item.played === true ? '已看过' : item.played === false ? '未看过' : '观看未知'
  const favorite = item.favorite === true ? '已收藏' : item.favorite === false ? '未收藏' : '收藏未知'
  return `${played} · ${favorite}`
}
