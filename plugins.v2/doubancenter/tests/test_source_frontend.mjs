import assert from 'node:assert/strict'
import { sourceDescriptor, doubanDispatchUrl } from '../src/components/source.js'

const config = {
  custom_ranks: [{
    key: 'custom_msgch1rx_bm4f4t',
    name: '近期热门国产剧',
    route: '/douban/list/tv_domestic',
    media_type: 'tv',
  }],
}

const first = sourceDescriptor('custom_msgch1rx_bm4f4t', {
  title: '天才，女友',
  year: '2026',
  link: '',
  source_link: 'https://m.douban.com/subject_collection/tv_domestic',
  douban_id: '36403345',
}, config)
const second = sourceDescriptor('custom_msgch1rx_bm4f4t', {
  title: '九门',
  year: '2026',
  link: '',
  source_link: 'https://m.douban.com/subject_collection/tv_domestic',
  douban_id: '26811535',
}, config)

assert.equal(first.url, 'https://movie.douban.com/subject/36403345/')
assert.equal(second.url, 'https://movie.douban.com/subject/26811535/')
assert.equal(first.appUrl, 'https://www.douban.com/doubanapp/dispatch?uri=/subject/36403345?subtype=tv&from=mdouban&open=app')
assert.equal(second.appUrl, 'https://www.douban.com/doubanapp/dispatch?uri=/subject/26811535?subtype=tv&from=mdouban&open=app')
assert.notEqual(first.url, second.url)
assert.notEqual(first.appUrl, second.appUrl)
assert.ok(!first.url.includes('subject_collection'))
assert.ok(!second.url.includes('subject_collection'))
assert.ok(!first.appUrl.includes('/movie/'))
assert.ok(!second.appUrl.includes('/movie/'))

const search = sourceDescriptor('custom_msgch1rx_bm4f4t', {
  title: '未知剧集',
  year: '2026',
  link: '',
  source_link: 'https://m.douban.com/subject_collection/tv_domestic',
}, config)
assert.equal(search.url, 'https://m.douban.com/search/?query=%E6%9C%AA%E7%9F%A5%E5%89%A7%E9%9B%86%202026')
assert.equal(search.appUrl, '')
assert.ok(!search.url.includes('subject_collection'))

const direct = sourceDescriptor('custom_msgch1rx_bm4f4t', {
  title: '有直链',
  link: 'https://movie.douban.com/subject/12345678/',
  source_link: 'https://m.douban.com/subject_collection/tv_domestic',
}, config)
assert.equal(direct.url, 'https://movie.douban.com/subject/12345678/')
assert.equal(direct.appUrl, 'https://www.douban.com/doubanapp/dispatch?uri=/subject/12345678?subtype=tv&from=mdouban&open=app')

const movie = sourceDescriptor('movie_weekly', {
  title: '这个杀手不太冷',
  media_type: 'movie',
  douban_id: '1295644',
}, {})
assert.equal(movie.appUrl, 'https://www.douban.com/doubanapp/dispatch?uri=/movie/1295644?from=mdouban&open=app')
assert.equal(doubanDispatchUrl('1295644', 'movie'), 'https://www.douban.com/doubanapp/dispatch?uri=/movie/1295644?from=mdouban&open=app')

const otherRoute = sourceDescriptor('custom_other', {
  title: '其他 RSS 条目',
  year: '2025',
  link: '',
  source_link: 'https://rsshub.example/anime/feed',
}, {
  custom_ranks: [{ key: 'custom_other', route: '/anime/feed', name: '其他 RSS', media_type: 'auto' }],
})
assert.equal(otherRoute.url, 'https://m.douban.com/search/?query=%E5%85%B6%E4%BB%96%20RSS%20%E6%9D%A1%E7%9B%AE%202025')
assert.equal(otherRoute.appUrl, '')
assert.ok(!otherRoute.url.includes('rsshub.example'))

console.log('source frontend behavior: ok')
