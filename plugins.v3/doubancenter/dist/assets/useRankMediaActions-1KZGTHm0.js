import { a as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-tazMeCBU.js';

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
  const route = stringValue(item?.rank_route || item?.route || custom?.route);
  if (/\/movie(?:[/?#]|_|$)/i.test(route)) return 'movie'
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
  if (stringValue(item?.media_source).toLowerCase() === 'douban') return stringValue(item?.media_id)
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
  const isBangumi = stringValue(item?.media_source).toLowerCase() === 'bangumi' || rankKey === 'bangumi' || isBangumiLink(link) || isBangumiLink(sourceLink) || /(?:^|\/)bangumi(?:\.tv)?(?:\/|$)/i.test(route);
  if (isBangumi) {
    return { label: 'Bgm', icon: 'mdi-link-variant', color: '#F838A0', url: link || sourceLink }
  }

  const isDouban = stringValue(item?.media_source).toLowerCase() === 'douban' || Boolean(item?.douban_id || item?.doubanid) || isDoubanHost(link) || isDoubanHost(sourceLink) || isDoubanRoute(route);
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

function currentValue(value) {
  return typeof value === 'function' ? value() : value
}


function useRankMediaActions({ api, pluginId, rankNameOf }) {
  function queryString(params) {
    return Object.entries(params || {})
      .filter(([, value]) => value !== undefined && value !== null && value !== '')
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
      .join('&')
  }

  function normalizeApiData(value) {
    if (value && typeof value === 'object' && Object.prototype.hasOwnProperty.call(value, 'success')) {
      return value.success === false ? value : value.data
    }
    return value
  }

  function mediaIdOf(media) {
    if (media?.media_source && media?.media_id) return `${media.media_source}:${media.media_id}`
    if (media?.tmdb_id) return `tmdb:${media.tmdb_id}`
    if (media?.douban_id) return `douban:${media.douban_id}`
    if (media?.bangumi_id) return `bangumi:${media.bangumi_id}`
    if (media?.media_id && media?.mediaid_prefix) return `${media.mediaid_prefix}:${media.media_id}`
    return ''
  }

  function tmdbIdOf(media) {
    if (media?.tmdb_id || media?.tmdbid) return media.tmdb_id || media.tmdbid
    return ['themoviedb', 'tmdb'].includes(String(media?.media_source || '').toLowerCase()) ? media?.media_id || '' : ''
  }

  function bangumiIdOf(rk, item) {
    if (item?.bangumi_id || item?.bangumiid) return item.bangumi_id || item.bangumiid
    if (String(item?.media_source || '').toLowerCase() === 'bangumi') return item?.media_id || ''
    if (rk === 'bangumi' && item?.douban_id) return item.douban_id
    const match = String(item?.link || '').match(/(?:bgm\.tv|bangumi\.tv)\/subject\/(\d+)/);
    return match ? match[1] : ''
  }

  function mediaTypeOf(rk, item) {
    const type = item?.media_type || item?.mtype || item?.type || '';
    if (type === '电影' || type === 'movie') return 'movie'
    if (type === '电视剧' || type === 'tv') return 'tv'
    return rk === 'movie_weekly' ? 'movie' : 'tv'
  }

  async function resolveRankMedia(rk, item) {
    const mediaType = mediaTypeOf(rk, item);
    const params = queryString({
      media_source: item?.media_source || '',
      media_id: item?.media_id || '',
      tmdb_id: item?.tmdbid || item?.tmdb_id || '',
      bangumi_id: bangumiIdOf(rk, item),
      media_type: mediaType,
      title: item?.title || item?.name || '',
      year: item?.year || '',
      season: item?.season || '',
    });
    const res = normalizeApiData(
      await getPluginApi(currentValue(api), currentValue(pluginId), `resolve_media?${params}`),
    );
    if (res?.success === false) throw new Error(res?.message || '媒体识别失败')
    const media = res?.data && !Array.isArray(res.data) ? res.data : res;
    if (!media || typeof media !== 'object') throw new Error('媒体识别失败')
    const merged = { ...item, ...media };
    merged.title = media.title || media.name || item?.title || item?.name || '';
    merged.name = media.name || media.title || item?.name || item?.title || '';
    merged.year = media.year || item?.year || '';
    merged.type = media.type || (mediaType === 'movie' ? '电影' : '电视剧');
    merged.media_source = media.media_source || item?.media_source || null;
    merged.media_id = media.media_id || item?.media_id || null;
    merged.tmdb_id = media.tmdb_id || media.tmdbid || item?.tmdb_id || item?.tmdbid || null;
    merged.tmdbid = media.tmdbid || media.tmdb_id || item?.tmdbid || item?.tmdb_id || null;
    merged.douban_id = media.douban_id || media.doubanid || item?.douban_id || item?.doubanid || null;
    merged.doubanid = media.doubanid || media.douban_id || item?.doubanid || item?.douban_id || null;
    merged.bangumi_id = media.bangumi_id || media.bangumiid || bangumiIdOf(rk, item) || null;
    merged.bangumiid = media.bangumiid || media.bangumi_id || bangumiIdOf(rk, item) || null;
    if (!merged.media_source || !merged.media_id) {
      const mediaId = mediaIdOf(merged);
      if (mediaId) {
        const [prefix, id] = mediaId.split(':');
        merged.media_source = merged.media_source || prefix;
        merged.media_id = merged.media_id || id;
      }
    }
    return merged
  }

  async function requestRankSubscription(rk, item) {
    const params = queryString({
      media_source: item?.media_source || '',
      media_id: item?.media_id || '',
      tmdb_id: item?.tmdbid || item?.tmdb_id || '',
      bangumi_id: bangumiIdOf(rk, item),
      media_type: mediaTypeOf(rk, item),
      title: item?.title || item?.name || '',
      year: item?.year || '',
      rank_key: rk,
      rank_name: item?.rank_name || rankNameOf(rk, item),
      source_link: item?.link || '',
      season: item?.season || '',
    });
    return postPluginApi(currentValue(api), currentValue(pluginId), `subscribe?${params}`, {})
  }

  return {
    bangumiIdOf,
    mediaIdOf,
    mediaTypeOf,
    normalizeApiData,
    queryString,
    requestRankSubscription,
    resolveRankMedia,
    tmdbIdOf,
  }
}

export { doubanDispatchUrl as d, sourceDescriptor as s, useRankMediaActions as u };
