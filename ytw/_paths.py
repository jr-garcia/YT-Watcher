from os import path

currentDir = path.dirname(__file__)

iconPath = path.join(currentDir, 'icons')
brightPath = path.join(iconPath, 'Bright')
nuovolaPath = path.join(iconPath, 'Nuvola')

CACHESPATH = path.abspath(path.join(currentDir, 'caches'))
OPTIONSPATH = path.abspath(path.join(currentDir, 'options'))

cachedInfosPath = path.join(CACHESPATH, 'infos')
searchesPath = path.join(OPTIONSPATH, 'searches')
cachedThumbsPath = path.join(CACHESPATH, 'thumbs')

