import { getPluginApi, postPluginApi } from './api'


function currentValue(value) {
  return typeof value === 'function' ? value() : value
}


export function useRankMediaActions({ api, pluginId, rankNameOf }) {
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
    const match = String(item?.link || '').match(/(?:bgm\.tv|bangumi\.tv)\/subject\/(\d+)/)
    return match ? match[1] : ''
  }

  function mediaTypeOf(rk, item) {
    const type = item?.media_type || item?.mtype || item?.type || ''
    if (type === '电影' || type === 'movie') return 'movie'
    if (type === '电视剧' || type === 'tv') return 'tv'
    return rk === 'movie_weekly' ? 'movie' : 'tv'
  }

  async function resolveRankMedia(rk, item) {
    const mediaType = mediaTypeOf(rk, item)
    const params = queryString({
      media_source: item?.media_source || '',
      media_id: item?.media_id || '',
      tmdb_id: item?.tmdbid || item?.tmdb_id || '',
      bangumi_id: bangumiIdOf(rk, item),
      media_type: mediaType,
      title: item?.title || item?.name || '',
      year: item?.year || '',
      season: item?.season || '',
    })
    const res = normalizeApiData(
      await getPluginApi(currentValue(api), currentValue(pluginId), `resolve_media?${params}`),
    )
    if (res?.success === false) throw new Error(res?.message || '媒体识别失败')
    const media = res?.data && !Array.isArray(res.data) ? res.data : res
    if (!media || typeof media !== 'object') throw new Error('媒体识别失败')
    const merged = { ...item, ...media }
    merged.title = media.title || media.name || item?.title || item?.name || ''
    merged.name = media.name || media.title || item?.name || item?.title || ''
    merged.year = media.year || item?.year || ''
    merged.type = media.type || (mediaType === 'movie' ? '电影' : '电视剧')
    merged.media_source = media.media_source || item?.media_source || null
    merged.media_id = media.media_id || item?.media_id || null
    merged.tmdb_id = media.tmdb_id || media.tmdbid || item?.tmdb_id || item?.tmdbid || null
    merged.tmdbid = media.tmdbid || media.tmdb_id || item?.tmdbid || item?.tmdb_id || null
    merged.douban_id = media.douban_id || media.doubanid || item?.douban_id || item?.doubanid || null
    merged.doubanid = media.doubanid || media.douban_id || item?.doubanid || item?.douban_id || null
    merged.bangumi_id = media.bangumi_id || media.bangumiid || bangumiIdOf(rk, item) || null
    merged.bangumiid = media.bangumiid || media.bangumi_id || bangumiIdOf(rk, item) || null
    if (!merged.media_source || !merged.media_id) {
      const mediaId = mediaIdOf(merged)
      if (mediaId) {
        const [prefix, id] = mediaId.split(':')
        merged.media_source = merged.media_source || prefix
        merged.media_id = merged.media_id || id
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
    })
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
