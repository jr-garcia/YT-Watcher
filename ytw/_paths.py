from os import path

currentDir = path.dirname(__file__)

iconPath = path.join(currentDir, 'icons')
brightPath = path.join(iconPath, 'Bright')

CACHESPATH = path.abspath(path.join(currentDir, 'caches'))

cachedInfosPath = path.join(CACHESPATH, 'infos')
cachedThumbsPath = path.join(CACHESPATH, 'thumbs')
thumbsCacheFilePath = path.join(CACHESPATH, 'thumbs.cache')

