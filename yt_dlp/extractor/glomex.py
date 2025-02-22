# coding: utf-8
from __future__ import unicode_literals

import re
import urllib.parse

from .common import InfoExtractor
from ..utils import (
    determine_ext,
    ExtractorError,
    int_or_none,
    parse_qs,
    smuggle_url,
    unescapeHTML,
    unsmuggle_url,
)


class GlomexBaseIE(InfoExtractor):
    _DEFAULT_ORIGIN_URL = 'https://player.glomex.com/'
    _API_URL = 'https://integration-cloudfront-eu-west-1.mes.glomex.cloud/'

    @staticmethod
    def _smuggle_origin_url(url, origin_url):
        if origin_url is None:
            return url
        return smuggle_url(url, {'origin': origin_url})

    @classmethod
    def _unsmuggle_origin_url(cls, url, fallback_origin_url=None):
        defaults = {'origin': fallback_origin_url or cls._DEFAULT_ORIGIN_URL}
        unsmuggled_url, data = unsmuggle_url(url, default=defaults)
        return unsmuggled_url, data['origin']

    def _get_videoid_type(self, video_id):
        _VIDEOID_TYPES = {
            'v': 'video',
            'pl': 'playlist',
            'rl': 'related videos playlist',
            'cl': 'curated playlist',
        }
        prefix = video_id.split('-')[0]
        return _VIDEOID_TYPES.get(prefix, 'unknown type')

    def _download_api_data(self, video_id, integration, current_url=None):
        query = {
            'integration_id': integration,
            'playlist_id': video_id,
            'current_url': current_url or self._DEFAULT_ORIGIN_URL,
        }
        video_id_type = self._get_videoid_type(video_id)
        return self._download_json(
            self._API_URL,
            video_id, 'Downloading %s JSON' % video_id_type,
            'Unable to download %s JSON' % video_id_type,
            query=query)

    def _download_and_extract_api_data(self, video_id, integration, current_url):
        api_data = self._download_api_data(video_id, integration, current_url)
        videos = api_data['videos']
        if not videos:
            raise ExtractorError('no videos found for %s' % video_id)
        videos = [self._extract_api_data(video, video_id) for video in videos]
        return videos[0] if len(videos) == 1 else self.playlist_result(videos, video_id)

    def _extract_api_data(self, video, video_id):
        if video.get('error_code') == 'contentGeoblocked':
            self.raise_geo_restricted(countries=video['geo_locations'])

        formats, subs = [], {}
        for format_id, format_url in video['source'].items():
            ext = determine_ext(format_url)
            if ext == 'm3u8':
                formats_, subs_ = self._extract_m3u8_formats_and_subtitles(
                    format_url, video_id, 'mp4', m3u8_id=format_id,
                    fatal=False)
                formats.extend(formats_)
                self._merge_subtitles(subs_, target=subs)
            else:
                formats.append({
                    'url': format_url,
                    'format_id': format_id,
                })
        if video.get('language'):
            for fmt in formats:
                fmt['language'] = video['language']
        self._sort_formats(formats)

        images = (video.get('images') or []) + [video.get('image') or {}]
        thumbnails = [{
            'id': image.get('id'),
            'url': f'{image["url"]}/profile:player-960x540',
            'width': 960,
            'height': 540,
        } for image in images if image.get('url')]
        self._remove_duplicate_formats(thumbnails)

        return {
            'id': video.get('clip_id') or video_id,
            'title': video.get('title'),
            'description': video.get('description'),
            'thumbnails': thumbnails,
            'duration': int_or_none(video.get('clip_duration')),
            'timestamp': video.get('created_at'),
            'formats': formats,
            'subtitles': subs,
        }


class GlomexIE(GlomexBaseIE):
    IE_NAME = 'glomex'
    IE_DESC = 'Glomex videos'
    _VALID_URL = r'https?://video\.glomex\.com/[^/]+/(?P<id>v-[^-]+)'
    _INTEGRATION_ID = '19syy24xjn1oqlpc'

    _TESTS = [{
        'url': 'https://video.glomex.com/sport/v-cb24uwg77hgh-nach-2-0-sieg-guardiola-mit-mancity-vor-naechstem-titel',
        'md5': 'cec33a943c4240c9cb33abea8c26242e',
        'info_dict': {
            'id': 'v-cb24uwg77hgh',
            'ext': 'mp4',
            'title': 'md5:38a90cedcfadd72982c81acf13556e0c',
            'description': 'md5:1ea6b6caff1443fcbbba159e432eedb8',
            'duration': 29600,
            'timestamp': 1619895017,
            'upload_date': '20210501',
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        return self.url_result(
            GlomexEmbedIE.build_player_url(video_id, self._INTEGRATION_ID, url),
            GlomexEmbedIE.ie_key(), video_id)


class GlomexEmbedIE(GlomexBaseIE):
    IE_NAME = 'glomex:embed'
    IE_DESC = 'Glomex embedded videos'
    _BASE_PLAYER_URL = '//player.glomex.com/integration/1/iframe-player.html'
    _BASE_PLAYER_URL_RE = re.escape(_BASE_PLAYER_URL).replace('/1/', r'/[^/]/')
    _VALID_URL = rf'https?:{_BASE_PLAYER_URL_RE}\?([^#]+&)?playlistId=(?P<id>[^#&]+)'

    _TESTS = [{
        'url': 'https://player.glomex.com/integration/1/iframe-player.html?integrationId=4059a013k56vb2yd&playlistId=v-cfa6lye0dkdd-sf',
        'md5': '68f259b98cc01918ac34180142fce287',
        'info_dict': {
            'id': 'v-cfa6lye0dkdd-sf',
            'ext': 'mp4',
            'timestamp': 1635337199,
            'duration': 133080,
            'upload_date': '20211027',
            'description': 'md5:e741185fc309310ff5d0c789b437be66',
            'title': 'md5:35647293513a6c92363817a0fb0a7961',
        },
    }, {
        'url': 'https://player.glomex.com/integration/1/iframe-player.html?origin=fullpage&integrationId=19syy24xjn1oqlpc&playlistId=rl-vcb49w1fb592p&playlistIndex=0',
        'info_dict': {
            'id': 'rl-vcb49w1fb592p',
        },
        'playlist_count': 100,
    }, {
        'url': 'https://player.glomex.com/integration/1/iframe-player.html?playlistId=cl-bgqaata6aw8x&integrationId=19syy24xjn1oqlpc',
        'info_dict': {
            'id': 'cl-bgqaata6aw8x',
        },
        'playlist_mincount': 2,
    }]

    @classmethod
    def build_player_url(cls, video_id, integration, origin_url=None):
        query_string = urllib.parse.urlencode({
            'playlistId': video_id,
            'integrationId': integration,
        })
        return cls._smuggle_origin_url(f'https:{cls._BASE_PLAYER_URL}?{query_string}', origin_url)

    @classmethod
    def _extract_urls(cls, webpage, origin_url):
        VALID_SRC = rf'(?:https?:)?{cls._BASE_PLAYER_URL_RE}\?(?:(?!(?P=_q1)).)+'

        # https://docs.glomex.com/publisher/video-player-integration/javascript-api/
        EMBED_RE = r'''(?x)(?:
            <iframe[^>]+?src=(?P<_q1>%(quot_re)s)(?P<url>%(url_re)s)(?P=_q1)|
            <(?P<html_tag>glomex-player|div)(?:
                data-integration-id=(?P<_q2>%(quot_re)s)(?P<integration_html>(?:(?!(?P=_q2)).)+)(?P=_q2)|
                data-playlist-id=(?P<_q3>%(quot_re)s)(?P<id_html>(?:(?!(?P=_q3)).)+)(?P=_q3)|
                data-glomex-player=(?P<_q4>%(quot_re)s)(?P<glomex_player>true)(?P=_q4)|
                [^>]*?
            )+>|
            # naive parsing of inline scripts for hard-coded integration parameters
            <(?P<script_tag>script)[^<]*?>(?:
                (?P<_stjs1>dataset\.)?integrationId\s*(?(_stjs1)=|:)\s*
                    (?P<_q5>%(quot_re)s)(?P<integration_js>(?:(?!(?P=_q5)).)+)(?P=_q5)\s*(?(_stjs1);|,)?|
                (?P<_stjs2>dataset\.)?playlistId\s*(?(_stjs2)=|:)\s*
                    (?P<_q6>%(quot_re)s)(?P<id_js>(?:(?!(?P=_q6)).)+)(?P=_q6)\s*(?(_stjs2);|,)?|
                (?:\s|.)*?
            )+</script>
        )''' % {'quot_re': r'["\']', 'url_re': VALID_SRC}

        for mtup in re.findall(EMBED_RE, webpage):
            # re.finditer causes a memory spike. See https://github.com/yt-dlp/yt-dlp/issues/2512
            mdict = dict(zip((
                'url', '_',
                'html_tag', '_', 'integration_html', '_', 'id_html', '_', 'glomex_player',
                'script_tag', '_', '_', 'integration_js', '_', 'id_js',
            ), mtup))
            if mdict.get('url'):
                url = unescapeHTML(mdict['url'])
                if not cls.suitable(url):
                    continue
                yield cls._smuggle_origin_url(url, origin_url)
            elif mdict.get('html_tag'):
                if mdict['html_tag'] == 'div' and not mdict.get('glomex_player'):
                    continue
                if not mdict.get('video_id_html') or not mdict.get('integration_html'):
                    continue
                yield cls.build_player_url(mdict['video_id_html'], mdict['integration_html'], origin_url)
            elif mdict.get('script_tag'):
                if not mdict.get('video_id_js') or not mdict.get('integration_js'):
                    continue
                yield cls.build_player_url(mdict['video_id_js'], mdict['integration_js'], origin_url)

    def _real_extract(self, url):
        url, origin_url = self._unsmuggle_origin_url(url)
        playlist_id = self._match_id(url)
        integration = parse_qs(url).get('integrationId', [None])[0]
        if not integration:
            raise ExtractorError('No integrationId in URL', expected=True)
        return self._download_and_extract_api_data(playlist_id, integration, origin_url)
