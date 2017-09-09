from multiprocessing import Process, Queue
from traceback import format_exc
from queue import Empty, Full
from time import time, sleep
from os import path
from urllib.error import *

from .youtube_dl.YoutubeDL import YoutubeDL, ExtractorError
from .youtube_dl.utils import *

from .Downloading import download
from ._paths import cachedThumbsPath

SORTINGDICT = {0: '', 1: 'Date'}
MAXRETRIES = 3


class ErrorTypesEnum(object):
    NonValidData = 'NonValidData'
    PageNonAccesible = 'PageNonAccesible'
    Other = 'Other'


class TaskTypesEnum(object):
    word = 'word'
    video = 'video'
    thumb = 'thumb'
    data = 'data'
    error = 'error'


class NonValidDataError(BaseException):
    def __init__(self, msg, searchType, what):
        self.searchType = searchType
        self.what = what
        self.msg = str(msg)


class Searcher(Process):
    def __init__(self):

        super(Searcher, self).__init__()

        self.searchOrder = 'Date'
        self.searchMax = 50
        self.local = Queue()
        self.local.cancel_join_thread()
        self.remote = None

        self.thumbsCachePath = ''

        self._isRunning = True
        self.externalPause = False

        self.downloader = self.createDownloader()
        self.searchExtractor = self.createSearcher()
        self.resultsExtractor = self.downloader.get_info_extractor('Youtube')

    def createDownloader(self):
        sorting = 'ytsearch'
        if self.searchOrder == 'Date':
            sorting += 'date'
        ytOptions = {'logger': MyLogger(), 'progress_hooks': [my_hook], 'default_search': sorting + str(self.searchMax)}
        return YoutubeDL(ytOptions)

    def createSearcher(self):
        return self.downloader.get_info_extractor('YoutubeSearch' + self.searchOrder)

    def prepareConnections(self, remote):
        self.remote = remote
        return self.local

    def search(self, what, searchType):
        try:
            if searchType == TaskTypesEnum.word:
                ydl = self.downloader
                query = ydl.get_info_extractor('Generic').extract(what)
                url = query['url']
                searchExtractor = self.searchExtractor
                result = searchExtractor.extract(url)
                ydl.add_default_extra_info(result, searchExtractor, url)
                return result
            elif searchType == TaskTypesEnum.video:
                resultsExtractor = self.resultsExtractor
                videoInfo = resultsExtractor.extract(what)
                if not self.hasEssentialData(videoInfo):
                    raise NonValidDataError('Null uploader', searchType, what)
                if videoInfo['like_count'] is None:
                    videoInfo['like_count'] = 0
                if videoInfo['dislike_count'] is None:
                    videoInfo['dislike_count'] = 0
                return videoInfo
            elif searchType == TaskTypesEnum.thumb:
                thumbURL, videoID = what
                binaryThumb = download(thumbURL)
                thumbExt = path.splitext(path.basename(thumbURL))[1]
                thumbPath = path.join(cachedThumbsPath, '_' + videoID + '_thumb' + thumbExt)
                try:
                    with open(thumbPath, 'xb') as thumbFile:
                        thumbFile.write(binaryThumb)
                except FileExistsError:
                    pass
                return videoID, thumbPath
            else:  # searchType == TaskTypesEnum.data:
                binaryData = download(what)
                return binaryData
        except Exception:
            remoteRaise(self.local)

    def hasEssentialData(self, videoInfo):
        try:
            if None in (videoInfo['uploader'], videoInfo['uploader_url'], videoInfo['upload_date']):
                return False
            else:
                return True
        except KeyError:
            remoteRaise(self.local)

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

                    self.searchOrder = SORTINGDICT[data.sorting]
                    self.searchMax = data.maxResults
                    self.downloader = self.createDownloader()
                    self.searchExtractor = self.createSearcher()

                    query, searchType = data
                    try:
                        result = self.search(query, searchType)
                        data = None
                        if result is not None:
                            self.local.put(TaskResult(result, searchType))
                    except (NonValidDataError, YoutubeDLError):
                        retries += 1
                        if retries == MAXRETRIES:
                            remoteRaise(self.local)
                        else:
                            sleep(1)
                    except:
                        remoteRaise(self.local)
                        self.terminate()
                        raise

            except:
                self._isRunning = False
                try:
                    self.local.put_nowait(RemoteError(format_exc(), ErrorTypesEnum.Other))
                except:
                    pass
                remoteRaise(self.local)
                self.terminate()
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


def remoteRaise(queue):
    eType, instance, tb = sys.exc_info()
    if eType == NonValidDataError:
        errorType = ErrorTypesEnum.NonValidData
        data = 'Null uploader'
    elif issubclass(eType, YoutubeDLError):
        if isinstance(instance, DownloadError):
            cause = 'Download error'
        else:
            cause = instance.cause
        data = str(cause)
        if isinstance(cause, URLError):
            errorType = ErrorTypesEnum.PageNonAccesible
        else:
            errorType = ErrorTypesEnum.Other
    else:
        errorType = ErrorTypesEnum.Other
        data = str(instance)
    queue.put_nowait(TaskResult((data, errorType), TaskTypesEnum.error))
    

def isRemoteError(result):
    return isinstance(result, NonValidDataError) or issubclass(type(result), YoutubeDL)


class MyLogger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        print('Downloader warning: ' + msg)

    def error(self, msg):
        print('Downloader error: ' + msg)
        # raise NonValidDataError(msg)


def my_hook(d):
    print('status', d)
    if d['status'] == 'finished':
        print('Done downloading, now converting ...')


class TaskResult(object):
    def __init__(self, result, taskType):
        self.taskType = taskType
        if taskType == TaskTypesEnum.error:
            finalData = RemoteError(*result)
        else:
            finalData = result
        self.data = finalData

    def __repr__(self):
        return 'Task result:' + str(self.taskType)


class RemoteError(object):
    def __init__(self, *args):
        self.errorData = args[0]
        self.errorType = args[1]
