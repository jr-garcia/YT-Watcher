from multiprocessing import Process, Queue
from queue import Empty, Full
from time import time, sleep
from .youtube_dl.YoutubeDL import YoutubeDL, ExtractorError
from .youtube_dl.utils import *

from .Downloading import download

from os import path

from ._paths import cachedThumbsPath

MAXRETRIES = 5


class SearchTypesEnum(object):
    word = 'word'
    video = 'video'
    thumb = 'thumb'
    error = 'error'


class DownloaderError(Exception):
    def __init__(self, msg):
        self.msg = str(msg)


class Searcher(Process):
    def __init__(self):

        super(Searcher, self).__init__()

        self.local = Queue()
        self.local.cancel_join_thread()
        self.remote = None

        self.thumbsCachePath = ''

        self._isRunning = True
        self.externalPause = False

        ytOptions = {'logger': MyLogger(), 'progress_hooks': [my_hook], 'default_search': 'ytsearch7'}

        self.downloader = YoutubeDL(ytOptions)
        self.searchExtractor = self.downloader.get_info_extractor('YoutubeSearch')
        self.resultsExtractor = self.downloader.get_info_extractor('Youtube')

    def prepareConnections(self, remote):
        self.remote = remote
        return self.local

    def _doSearch(self, what, searchType):
        try:
            if searchType == SearchTypesEnum.word:
                ydl = self.downloader
                query = ydl.get_info_extractor('Generic').extract(what)
                url = query['url']
                searchExtractor = self.searchExtractor
                result = searchExtractor.extract(url)
                ydl.add_default_extra_info(result, searchExtractor, url)
                return result
            elif searchType == SearchTypesEnum.video:
                resultsExtractor = self.resultsExtractor
                videoInfo = resultsExtractor.extract(what)
                if not self.hasValidData(videoInfo):
                    videoInfo = resultsExtractor.extract(what)
                    if not self.hasValidData(videoInfo):
                        raise YoutubeDLError('Null uploader or like_count')
                if videoInfo['like_count'] is None:
                    videoInfo['like_count'] = 0
                if videoInfo['dislike_count'] is None:
                    videoInfo['dislike_count'] = 0
                return videoInfo
            else:
                thumbURL, videoID = what
                binaryThumb = download(thumbURL)
                thumbExt = path.splitext(path.basename(thumbURL))[1]
                thumbPath = path.join(cachedThumbsPath, '_' + videoID + '_thumb' + thumbExt)
                with open(thumbPath, 'xb') as thumbFile:
                    thumbFile.write(binaryThumb)

                return videoID, thumbPath

        except Exception as error:
            raise error

    def hasValidData(self, videoInfo):
        if videoInfo['uploader'] is None:
            return False
        else:
            return True

    def run(self):
        data = None
        retries = 0
        while self._isRunning:
            try:
                if data is None:
                    try:
                        data = self.remote.get(timeout=3)
                        retries = 0
                    except Empty:
                        pass
                    except:
                        self._isRunning = False

                if data is None:
                    continue
                elif data == '':
                    self.terminate()
                    return
                elif data == 'pause':
                    self.externalPause = True
                elif data == 'unpause':
                    self.externalPause = False
                else:
                    if self.externalPause:
                        continue
                    query, searchType = data
                    try:
                        result = self._doSearch(query, searchType)
                        data = None
                        self.local.put((result, searchType))
                    except YoutubeDLError as error:
                        retries += 1
                        if retries == MAXRETRIES:
                            self.local.put((DownloaderError(error), searchType))
                        else:
                            sleep(1)

            except:
                self._isRunning = False
                raise

        self.terminate()

    def terminate(self):
        self._isRunning = False
        if self.local is not None:
            self.local.close()
        try:
            super(Searcher, self).terminate()
        except AttributeError:
            pass


class MyLogger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        if 'unable to extract' in msg:
            raise ExtractorError(msg)         
        print('Downloader warning: ' + msg)

    def error(self, msg):
        print('Downloader error: ' + msg)


def my_hook(d):
    print('status', d)
    if d['status'] == 'finished':
        print('Done downloading, now converting ...')
