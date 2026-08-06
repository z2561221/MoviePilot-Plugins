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

function isCustomRank(rankKey, config) {
  return stringValue(rankKey).startsWith('custom_') || (config?.custom_ranks || []).some(entry => entry?.key === rankKey)
}

function doubanSubjectUrl(subjectId) {
  return `https://movie.douban.com/subject/${encodeURIComponent(stringValue(subjectId))}/`
}

function mediaSubtypeOf(rankKey, item, config) {
  const rawType = stringValue(item?.media_type || item?.mtype || item?.type).toLowerCase();
  if (rawType === 'movie' || rawType === '电影') return 'movie'
  if (rawType === 'tv' || rawType === '电视剧') return 'tv'
  const custom = (config?.custom_ranks || []).find(entry => entry?.key === rankKey);
  if (custom?.media_type === 'movie') return 'movie'
  if (custom?.media_type === 'tv') return 'tv'
  return rankKey === 'movie_weekly' ? 'movie' : 'tv'
}

function doubanDispatchUrl(subjectId, mediaType = 'tv') {
  const id = stringValue(subjectId);
  if (!id) return ''
  const subtype = mediaType === 'movie' || mediaType === '电影' ? 'movie' : 'tv';
  const uri = subtype === 'movie'
    ? `/movie/${encodeURIComponent(id)}?from=mdouban&open=app`
    : `/subject/${encodeURIComponent(id)}?subtype=tv&from=mdouban&open=app`;
  // 豆瓣原生榜单使用未编码的 uri 参数，dispatch 页面才能继续唤起 douban:// 深链。
  return `https://www.douban.com/doubanapp/dispatch?uri=${uri}`
}

function doubanSearchUrl(item) {
  const title = stringValue(item?.title || item?.name);
  const year = stringValue(item?.year);
  const query = [title, year].filter(Boolean).join(' ');
  return query ? `https://m.douban.com/search/?query=${encodeURIComponent(query)}` : ''
}

function isDoubanSubjectLink(value) {
  if (!isDoubanHost(value)) return false
  try {
    return /^\/subject\/\d+(?:\/|$)/i.test(new URL(stringValue(value)).pathname)
  } catch {
    return false
  }
}

function subjectIdOf(item) {
  const subjectId = item?.douban_id || item?.doubanid;
  if (subjectId) return stringValue(subjectId)
  const link = stringValue(item?.link);
  const match = link.match(/\/subject\/(\d+)/i);
  return match ? match[1] : ''
}

function doubanSourceUrl(item) {
  const subjectId = subjectIdOf(item);
  if (subjectId) return doubanSubjectUrl(subjectId)
  const link = stringValue(item?.link);
  if (isDoubanSubjectLink(link)) return link
  return doubanSearchUrl(item)
}

function doubanAppUrl(rankKey, item, config) {
  const subjectId = subjectIdOf(item);
  return subjectId ? doubanDispatchUrl(subjectId, mediaSubtypeOf(rankKey, item, config)) : ''
}

function sourceDescriptor(rankKey, item, config) {
  const link = stringValue(item?.link);
  const sourceLink = stringValue(item?.source_link);
  const route = rankRouteOf(rankKey, item, config);
  const customRank = isCustomRank(rankKey, config);
  const isBangumi = rankKey === 'bangumi' || isBangumiLink(link) || isBangumiLink(sourceLink) || /(?:^|\/)bangumi(?:\.tv)?(?:\/|$)/i.test(route);
  if (isBangumi) {
    return { label: 'Bgm', icon: 'mdi-link-variant', color: '#F838A0', url: link || sourceLink }
  }

  const isDouban = Boolean(item?.douban_id || item?.doubanid) || isDoubanHost(link) || isDoubanHost(sourceLink) || isDoubanRoute(route);
  if (isDouban || customRank) {
    return {
      label: '豆瓣',
      icon: 'mdi-open-in-new',
      color: '#08B810',
      url: doubanSourceUrl(item),
      appUrl: doubanAppUrl(rankKey, item, config),
    }
  }

  return { label: '详情', icon: 'mdi-link-variant', color: 'primary', url: link || sourceLink }
}

export { doubanDispatchUrl as d, sourceDescriptor as s };
