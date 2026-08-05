const BUILTIN_RANK_ROUTES = {
  coming: '/douban/tv/coming',
  tv_real_time: '/douban/list/tv_real_time_hotest',
  tv_chinese: '/douban/list/tv_chinese_best_weekly',
  tv_global: '/douban/list/tv_global_best_weekly',
  movie_weekly: '/douban/list/movie_weekly_best',
  bangumi: '/bangumi.tv/anime/followrank',
};

function stringValue(value) {
  return String(value || '').trim()
}

function isDoubanHost(value) {
  try {
    const host = new URL(stringValue(value)).hostname.toLowerCase();
    return host === 'douban.com' || host.endsWith('.douban.com')
  } catch {
    return false
  }
}

function isBangumiLink(value) {
  return /(?:^|\/\/)(?:www\.)?(?:bgm\.tv|bangumi\.tv)(?:\/|$)/i.test(stringValue(value))
}

function routePath(value) {
  const raw = stringValue(value);
  if (!raw) return ''
  try {
    return new URL(raw, 'https://rsshub.local').pathname
  } catch {
    return raw.split(/[?#]/, 1)[0]
  }
}

function isDoubanRoute(value) {
  return /^\/douban(?:\/|$)/i.test(routePath(value))
}

function rankRouteOf(rankKey, item, config) {
  if (item?.rank_route || item?.route) return stringValue(item.rank_route || item.route)
  const custom = (config?.custom_ranks || []).find(entry => entry?.key === rankKey);
  return stringValue(custom?.route || BUILTIN_RANK_ROUTES[rankKey])
}

function doubanCollectionUrl(route) {
  const match = routePath(route).match(/^\/douban\/(?:list|tv|subject_collection)\/([^/?#]+)/i);
  if (!match) return ''
  let collection = match[1];
  try {
    collection = decodeURIComponent(collection);
  } catch {
    // Keep the original slug when a user-provided route contains malformed escapes.
  }
  return `https://m.douban.com/subject_collection/${encodeURIComponent(collection)}`
}

function doubanSubjectUrl(subjectId) {
  return `https://www.douban.com/doubanapp/dispatch?uri=/movie/${encodeURIComponent(stringValue(subjectId))}?from=mdouban&open=app`
}

function doubanSearchUrl(item) {
  const title = stringValue(item?.title || item?.name);
  return title ? `https://m.douban.com/search/?query=${encodeURIComponent(title)}` : ''
}

function doubanSourceUrl(item, route) {
  const subjectId = item?.douban_id || item?.doubanid;
  if (subjectId) return doubanSubjectUrl(subjectId)
  const link = stringValue(item?.link);
  if (isDoubanHost(link)) return link
  const sourceLink = stringValue(item?.source_link);
  if (isDoubanHost(sourceLink)) return sourceLink
  const collectionUrl = doubanCollectionUrl(route);
  if (collectionUrl) return collectionUrl
  return isDoubanRoute(route) ? doubanSearchUrl(item) : ''
}

function sourceDescriptor(rankKey, item, config) {
  const link = stringValue(item?.link);
  const sourceLink = stringValue(item?.source_link);
  const route = rankRouteOf(rankKey, item, config);
  const isBangumi = rankKey === 'bangumi' || isBangumiLink(link) || isBangumiLink(sourceLink) || /(?:^|\/)bangumi(?:\.tv)?(?:\/|$)/i.test(route);
  if (isBangumi) {
    return { label: 'Bgm', icon: 'mdi-link-variant', color: '#F838A0', url: link || sourceLink }
  }

  const isDouban = Boolean(item?.douban_id || item?.doubanid) || isDoubanHost(link) || isDoubanHost(sourceLink) || isDoubanRoute(route);
  if (isDouban) {
    return { label: '豆瓣', icon: 'mdi-open-in-new', color: '#08B810', url: doubanSourceUrl(item, route) }
  }

  return { label: '详情', icon: 'mdi-link-variant', color: 'primary', url: link || sourceLink }
}

export { sourceDescriptor as s };
