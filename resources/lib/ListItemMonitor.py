#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import xbmc
import xbmcplugin
import xbmcaddon
import xbmcgui
import threading
import thread
import xbmcvfs
import random
import xml.etree.ElementTree as etree
import base64
import time
from random import randint
from Utils import *


class ListItemMonitor(threading.Thread):
    
    event = None
    exit = False
    delayedTaskInterval = 1795
    lastWeatherNotificationCheck = None
    lastNextAiredNotificationCheck = None
    liPath = ""
    liPathLast = ""
    liLabel = ""
    liLabelLast = ""
    folderPath = ""
    folderPathLast = ""
    unwatched = 1
    lastMusicDbId = ""
    lastpvrDbId = ""
    contentType = ""
    lastListItem = ""
    allStudioLogos = {}
    allStudioLogosColor = {}
    LastCustomStudioImagesPath = ""
    delayedTaskInterval = 1800
    widgetTaskInterval = 590
    moviesetCache = {}
    extraFanartCache = {}
    musicArtCache = {}
    streamdetailsCache = {}
    pvrArtCache = {}
    rottenCache = {}
    cachePath = os.path.join(ADDON_DATA_PATH,"librarycache.json")
    widgetCachePath = os.path.join(ADDON_DATA_PATH,"widgetscache.json")
    
    def __init__(self, *args):
        logMsg("HomeMonitor - started")
        self.event =  threading.Event()
        threading.Thread.__init__(self, *args)
    
    def stop(self):
        logMsg("HomeMonitor - stop called",0)
        self.saveCacheToFile()
        self.exit = True
        self.event.set()

    def run(self):
        
        self.getCacheFromFile()

        while (self.exit != True):
        
            if not xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)"):
        
                #set some globals
                self.liPath = xbmc.getInfoLabel("ListItem.Path").decode('utf-8')
                self.liLabel = xbmc.getInfoLabel("ListItem.Label").decode('utf-8')
                self.folderPath = xbmc.getInfoLabel("Container.FolderPath").decode('utf-8')
                curListItem = self.liPath + self.liLabel
                
                #perform actions if the container path has changed
                #always wait for the contenttype because plugins can be slow
                if self.folderPath and self.folderPath != self.folderPathLast or not self.contentType:
                    self.contentType = getCurrentContentType()
                    self.setForcedView()
                    self.focusEpisode()
                elif not self.folderPath and self.folderPathLast:
                    self.folderPathLast = None
                    self.resetWindowProps()
                
                #only perform actions when the listitem has actually changed
                if curListItem and curListItem != self.lastListItem and self.contentType:
                    
                    #clear all window props first
                    self.resetWindowProps()
                    
                    # monitor listitem props when musiclibrary is active
                    if xbmc.getCondVisibility("Window.IsActive(musiclibrary) | Window.IsActive(MyMusicSongs.xml)"):
                        try:
                            self.checkMusicArt()
                            self.setGenre()
                        except Exception as e:
                            logMsg("ERROR in checkMusicArt ! --> " + str(e), 0)
                                
                    # monitor listitem props when videolibrary is active
                    elif xbmc.getCondVisibility("Window.IsActive(videos) | Window.IsActive(movieinformation)"):
                        try:
                            self.setDuration()
                            self.setStudioLogo()
                            self.setGenre()
                            self.setDirector()
                            self.checkExtraFanArt()
                            self.setMovieSetDetails()
                            self.setAddonName()
                            self.setStreamDetails()
                            self.setRottenRatings()
                        except Exception as e:
                            logMsg("ERROR in LibraryMonitor ! --> " + str(e), 0)
                    
                    # monitor listitem props when PVR is active
                    elif xbmc.getCondVisibility("Window.IsActive(MyPVRChannels.xml) | Window.IsActive(MyPVRGuide.xml) | Window.IsActive(MyPVRTimers.xml) | Window.IsActive(MyPVRSearch.xml) | Window.IsActive(MyPVRRecordings.xml)"):
                        try:
                            self.setDuration()
                            self.setPVRThumbs()
                            self.setGenre()
                        except Exception as e:
                            logMsg("ERROR in LibraryMonitor ! --> " + str(e), 0)
                            
                    #set some globals
                    self.liPathLast = self.liPath
                    self.folderPathLast = self.folderPath
                    self.liLabelLast = self.liLabel
                    self.lastListItem = curListItem
                
                #monitor listitem props when home active
                elif xbmc.getCondVisibility("Window.IsActive(Home) + !IsEmpty(Window(home).Property(SkinHelper.WidgetContainer))"):
                    try:                
                        #set listitem window props for widget container
                        widgetContainer = WINDOW.getProperty("SkinHelper.WidgetContainer")
                        curListItem = xbmc.getInfoLabel("Container(%s).ListItem.Label" %widgetContainer)
                        if curListItem and curListItem != self.lastListItem:
                            self.setDuration(xbmc.getInfoLabel("Container(%s).ListItem.Duration" %widgetContainer))
                            self.setStudioLogo(xbmc.getInfoLabel("Container(%s).ListItem.Studio" %widgetContainer).decode('utf-8'))
                            self.setDirector(xbmc.getInfoLabel("Container(%s).ListItem.Director" %widgetContainer).decode('utf-8'))
                            self.setGenre(xbmc.getInfoLabel("Container(%s).ListItem.Genre" %widgetContainer).decode('utf-8'))
                            self.checkMusicArt(xbmc.getInfoLabel("Container(%s).ListItem.Artist" %widgetContainer).decode('utf-8')+xbmc.getInfoLabel("Container(%s).ListItem.Album" %widgetContainer).decode('utf-8'))
                            self.lastListItem = curListItem
                    except Exception as e:
                        logMsg("ERROR in LibraryMonitor HomeWidget ! --> " + str(e), 0)
                   
                #do some background stuff every 30 minutes
                if (self.delayedTaskInterval >= 1800):
                    thread.start_new_thread(self.doBackgroundWork, ())
                    self.delayedTaskInterval = 0          
                
                #reload some widgets every 10 minutes
                if (self.widgetTaskInterval >= 600):
                    self.resetGlobalWidgets()
                    self.widgetTaskInterval = 0
                
                #flush cache if videolibrary has changed
                if WINDOW.getProperty("resetVideoDbCache") == "reset":
                    self.moviesetCache = {}
                    self.extraFanartCache = {}
                    self.streamdetailsCache = {}
                    self.resetGlobalWidgets()
                    WINDOW.clearProperty("resetVideoDbCache")
                
                #flush cache if musiclibrary has changed
                if WINDOW.getProperty("resetMusicArtCache") == "reset":
                    self.lastMusicDbId = ""
                    self.musicArtCache = {}
                    WINDOW.clearProperty("resetMusicArtCache")
                else:
                    xbmc.sleep(100)
                    self.delayedTaskInterval += 0.1
                    self.widgetTaskInterval += 0.1

            else:
                #fullscreen video is playing
                xbmc.sleep(2000)
                self.delayedTaskInterval += 2
                self.widgetTaskInterval += 2
    
    def checkNetflixReady(self):
        if xbmc.getCondVisibility("System.HasAddon(plugin.video.netflixbmc)"):
            #set windowprop if netflix addon has a username filled in to prevent login loop box
            nfaddon = xbmcaddon.Addon(id='plugin.video.netflixbmc')
            if nfaddon.getSetting("username") and nfaddon.getSetting("html5MessageShown"):
                WINDOW.setProperty("netflixready","ready")
            else:
                WINDOW.clearProperty("netflixready")
    
    def resetGlobalWidgets(self):
        WINDOW.clearProperty("skinhelper-favourites")
        WINDOW.clearProperty("skinhelper-pvrrecordings")
        WINDOW.clearProperty("skinhelper-pvrchannels")
        WINDOW.clearProperty("skinhelper-nextairedtvshows")
        WINDOW.clearProperty("skinhelper-similarmovies")
        WINDOW.clearProperty("skinhelper-favouritemedia")
        WINDOW.setProperty("widgetreload2", datetime.now().strftime('%Y-%m-%d %H:%M:%S') + str(randint(0,9)))
                    
    def doBackgroundWork(self):
        try:
            logMsg("Started Background worker...",0)
            self.genericWindowProps()
            self.checkNetflixReady()
            self.updatePlexlinks()
            self.checkNotifications()
            self.getStudioLogos()
            #precache widgets listing
            getJSON('Files.GetDirectory','{ "directory": "plugin://script.skin.helper.service/?action=widgets", "media": "files" }')
            logMsg("Ended Background worker...",0)
        except Exception as e:
            logMsg("ERROR in HomeMonitor doBackgroundWork ! --> " + str(e), 0)
    
    def saveCacheToFile(self):
        #safety check: does the config directory exist?
        if not xbmcvfs.exists(ADDON_DATA_PATH + os.sep):
            xbmcvfs.mkdir(ADDON_DATA_PATH)
        
        libraryCache = {}
        libraryCache["MusicArtCache"] = self.musicArtCache
        libraryCache["PVRArtCache"] = self.pvrArtCache
        libraryCache["SetsCache"] = self.moviesetCache
        libraryCache["streamdetailsCache"] = self.streamdetailsCache
        libraryCache["rottenCache"] = self.rottenCache       
        json.dump(libraryCache, open(self.cachePath,'w'))
        
        #safe widget cache
        widgetCache = {}
        widget = WINDOW.getProperty("skinhelper-recommendedmovies")
        if widget: widgetCache["skinhelper-recommendedmovies"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-widgetcontenttype-persistant")
        if widget: widgetCache["skinhelper-widgetcontenttype"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-InProgressAndRecommendedMedia")
        if widget: widgetCache["skinhelper-InProgressAndRecommendedMedia"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-InProgressMedia")
        if widget: widgetCache["skinhelper-InProgressMedia"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-RecommendedMedia")
        if widget: widgetCache["skinhelper-RecommendedMedia"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-pvrrecordings")
        if widget: widgetCache["skinhelper-pvrrecordings"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-pvrchannels")
        if widget: widgetCache["skinhelper-pvrchannels"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-recentalbums")
        if widget: widgetCache["skinhelper-recentalbums"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-recentplayedalbums")
        if widget: widgetCache["skinhelper-recentplayedalbums"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-recentplayedsongs")
        if widget: widgetCache["skinhelper-recentplayedsongs"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-recentsongs")
        if widget: widgetCache["skinhelper-recentsongs"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-nextepisodes")
        if widget: widgetCache["skinhelper-nextepisodes"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-nextairedtvshows")
        if widget: widgetCache["skinhelper-nextairedtvshows"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-similarmovies")
        if widget: widgetCache["skinhelper-similarmovies"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-recentmedia")
        if widget: widgetCache["skinhelper-recentmedia"] = eval(widget)
        widget = WINDOW.getProperty("skinhelper-favouritemedia")
        if widget: widgetCache["skinhelper-favouritemedia"] = eval(widget)
        
        json.dump(widgetCache, open(self.widgetCachePath,'w'))
             
    def getCacheFromFile(self):
        try:
            if xbmcvfs.exists(self.cachePath):
                with open(self.cachePath) as data_file:    
                    data = json.load(data_file)
                    if data.has_key("MusicArtCache"):
                        self.musicArtCache = data["MusicArtCache"]
                    if data.has_key("SetsCache"):
                        self.moviesetCache = data["SetsCache"]
                    if data.has_key("streamdetailsCache"):
                        self.streamdetailsCache = data["streamdetailsCache"]
                    if data.has_key("rottenCache"):
                        self.rottenCache = data["rottenCache"]
                    if data.has_key("PVRArtCache"):
                        self.pvrArtCache = data["PVRArtCache"]
                        WINDOW.setProperty("SkinHelper.pvrArtCache",repr(data["PVRArtCache"]))
            #widgets cache
            if xbmcvfs.exists(self.widgetCachePath):
                with open(self.widgetCachePath) as data_file:    
                    data = json.load(data_file)
                    if data:
                        for key in data:
                            WINDOW.setProperty(key,repr(data[key]))
        except Exception as e:
            logMsg("ERROR in getCacheFromFile ! --> " + str(e), 0)

    def updatePlexlinks(self):
        
        if xbmc.getCondVisibility("System.HasAddon(plugin.video.plexbmc) + Skin.HasSetting(SmartShortcuts.plex)"): 
            logMsg("update plexlinks started...",0)
            
            #initialize plex window props by using the amberskin entrypoint for now
            if not WINDOW.getProperty("plexbmc.0.title"):
                xbmc.executebuiltin('RunScript(plugin.video.plexbmc,amberskin)')
                #wait for max 40 seconds untill the plex nodes are available
                count = 0
                while (count < 160 and not WINDOW.getProperty("plexbmc.0.title")):
                    xbmc.sleep(250)
                    count += 1
            
            #fallback to normal skin init
            if not WINDOW.getProperty("plexbmc.0.title"):
                xbmc.executebuiltin('RunScript(plugin.video.plexbmc,skin)')
                count = 0
                while (count < 80 and not WINDOW.getProperty("plexbmc.0.title")):
                    xbmc.sleep(250)
                    count += 1
            
            #get the plex setting if there are subnodes
            plexaddon = xbmcaddon.Addon(id='plugin.video.plexbmc')
            hasSecondayMenus = plexaddon.getSetting("secondary") == "true"
            del plexaddon
            
            #update plex window properties
            linkCount = 0
            while linkCount !=50:
                plexstring = "plexbmc." + str(linkCount)
                link = WINDOW.getProperty(plexstring + ".title")
                if not link:
                    break
                logMsg(plexstring + ".title --> " + link)
                plexType = WINDOW.getProperty(plexstring + ".type")
                logMsg(plexstring + ".type --> " + plexType)            

                if hasSecondayMenus == True:
                    recentlink = WINDOW.getProperty(plexstring + ".recent")
                    progresslink = WINDOW.getProperty(plexstring + ".ondeck")
                    alllink = WINDOW.getProperty(plexstring + ".all")
                else:
                    link = WINDOW.getProperty(plexstring + ".path")
                    alllink = link
                    link = link.replace("mode=1", "mode=0")
                    link = link.replace("mode=2", "mode=0")
                    recentlink = link.replace("/all", "/recentlyAdded")
                    progresslink = link.replace("/all", "/onDeck")
                    WINDOW.setProperty(plexstring + ".recent", recentlink)
                    WINDOW.setProperty(plexstring + ".ondeck", progresslink)
                    
                logMsg(plexstring + ".all --> " + alllink)
                
                WINDOW.setProperty(plexstring + ".recent.content", getContentPath(recentlink))
                WINDOW.setProperty(plexstring + ".recent.path", recentlink)
                WINDOW.setProperty(plexstring + ".recent.title", "recently added")
                logMsg(plexstring + ".recent --> " + recentlink)       
                WINDOW.setProperty(plexstring + ".ondeck.content", getContentPath(progresslink))
                WINDOW.setProperty(plexstring + ".ondeck.path", progresslink)
                WINDOW.setProperty(plexstring + ".ondeck.title", "on deck")
                logMsg(plexstring + ".ondeck --> " + progresslink)
                
                unwatchedlink = alllink.replace("mode=1", "mode=0")
                unwatchedlink = alllink.replace("mode=2", "mode=0")
                unwatchedlink = alllink.replace("/all", "/unwatched")
                WINDOW.setProperty(plexstring + ".unwatched", unwatchedlink)
                WINDOW.setProperty(plexstring + ".unwatched.content", getContentPath(unwatchedlink))
                WINDOW.setProperty(plexstring + ".unwatched.path", unwatchedlink)
                WINDOW.setProperty(plexstring + ".unwatched.title", "unwatched")
                
                WINDOW.setProperty(plexstring + ".content", getContentPath(alllink))
                WINDOW.setProperty(plexstring + ".path", alllink)
                
                linkCount += 1
                
            #add plex channels as entry - extract path from one of the nodes as a workaround because main plex addon channels listing is in error
            link = WINDOW.getProperty("plexbmc.0.path")
            
            if link:
                link = link.split("/library/")[0]
                link = link + "/channels/all&mode=21"
                link = link + ", return)"
                plexstring = "plexbmc.channels"
                WINDOW.setProperty(plexstring + ".title", "Channels")
                logMsg(plexstring + ".path --> " + link)
                WINDOW.setProperty(plexstring + ".path", link)
                WINDOW.setProperty(plexstring + ".content", getContentPath(link))
                
            logMsg("update plexlinks ended...",0)

    def checkNotifications(self):
        
        currentHour = time.strftime("%H")
        
        #weather notifications
        winw = xbmcgui.Window(12600)
        if (winw.getProperty("Alerts.RSS") and winw.getProperty("Current.Condition") and currentHour != self.lastWeatherNotificationCheck):
            dialog = xbmcgui.Dialog()
            dialog.notification(xbmc.getLocalizedString(31294), winw.getProperty("Alerts"), xbmcgui.NOTIFICATION_WARNING, 8000)
            self.lastWeatherNotificationCheck = currentHour
        
        #nextaired notifications
        if (xbmc.getCondVisibility("Skin.HasSetting(EnableNextAiredNotifications) + System.HasAddon(script.tv.show.next.aired)") and currentHour != self.lastNextAiredNotificationCheck):
            if (WINDOW.getProperty("NextAired.TodayShow")):
                dialog = xbmcgui.Dialog()
                dialog.notification(xbmc.getLocalizedString(31295), WINDOW.getProperty("NextAired.TodayShow"), xbmcgui.NOTIFICATION_WARNING, 8000)
                self.lastNextAiredNotificationCheck = currentHour
    
    def genericWindowProps(self):
        
        #GET TOTAL ADDONS COUNT       
        allAddonsCount = 0
        media_array = getJSON('Addons.GetAddons','{ }')
        for item in media_array:
            allAddonsCount += 1
        WINDOW.setProperty("SkinHelper.TotalAddons",str(allAddonsCount))
        
        addontypes = []
        addontypes.append( ["executable", "SkinHelper.TotalProgramAddons", 0] )
        addontypes.append( ["video", "SkinHelper.TotalVideoAddons", 0] )
        addontypes.append( ["audio", "SkinHelper.TotalAudioAddons", 0] )
        addontypes.append( ["image", "SkinHelper.TotalPicturesAddons", 0] )

        for type in addontypes:
            media_array = getJSON('Addons.GetAddons','{ "content": "%s" }' %type[0])
            for item in media_array:
                type[2] += 1
            WINDOW.setProperty(type[1],str(type[2]))    
                
        #GET FAVOURITES COUNT        
        allFavouritesCount = 0
        media_array = getJSON('Favourites.GetFavourites','{ }')
        for item in media_array:
            allFavouritesCount += 1
        WINDOW.setProperty("SkinHelper.TotalFavourites",str(allFavouritesCount))

        #GET TV CHANNELS COUNT
        if xbmc.getCondVisibility("Pvr.HasTVChannels"):
            allTvChannelsCount = 0
            media_array = getJSON('PVR.GetChannels','{"channelgroupid": "alltv" }' )
            for item in media_array:
                allTvChannelsCount += 1
            WINDOW.setProperty("SkinHelper.TotalTVChannels",str(allTvChannelsCount))        

        #GET RADIO CHANNELS COUNT
        if xbmc.getCondVisibility("Pvr.HasRadioChannels"):
            allRadioChannelsCount = 0
            media_array = getJSON('PVR.GetChannels','{"channelgroupid": "allradio" }' )
            for item in media_array:
                allRadioChannelsCount += 1
            WINDOW.setProperty("SkinHelper.TotalRadioChannels",str(allRadioChannelsCount))        
               
    def resetWindowProps(self):
        #reset window props
        WINDOW.clearProperty('SkinHelper.RottenTomatoesRating')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesAudienceRating')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesConsensus')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesAwards')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesBoxOffice')
        WINDOW.clearProperty("SkinHelper.PVR.Thumb") 
        WINDOW.clearProperty("SkinHelper.PVR.FanArt") 
        WINDOW.clearProperty("SkinHelper.PVR.ChannelLogo")
        WINDOW.clearProperty("SkinHelper.PVR.Poster")
        WINDOW.clearProperty("SkinHelper.ListItemStudioLogo")
        WINDOW.clearProperty('SkinHelper.ListItemDuration')
        WINDOW.setProperty("SkinHelper.ExtraFanArtPath","") 
        WINDOW.clearProperty("SkinHelper.Music.BannerArt") 
        WINDOW.clearProperty("SkinHelper.Music.LogoArt") 
        WINDOW.clearProperty("SkinHelper.Music.DiscArt")
        WINDOW.clearProperty("SkinHelper.Music.Info")
        WINDOW.clearProperty('SkinHelper.RottenTomatoesRating')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesAudienceRating')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesConsensus')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesAwards')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesBoxOffice')
        WINDOW.clearProperty("SkinHelper.PVR.Thumb") 
        WINDOW.clearProperty("SkinHelper.PVR.FanArt") 
        WINDOW.clearProperty("SkinHelper.PVR.ChannelLogo")
        WINDOW.clearProperty("SkinHelper.PVR.Poster")
        WINDOW.clearProperty("SkinHelper.Player.AddonName")
        WINDOW.clearProperty("SkinHelper.ForcedView")
        WINDOW.clearProperty('SkinHelper.MovieSet.Title')
        WINDOW.clearProperty('SkinHelper.MovieSet.Runtime')
        WINDOW.clearProperty('SkinHelper.MovieSet.Duration')
        WINDOW.clearProperty('SkinHelper.MovieSet.Duration.Hours')
        WINDOW.clearProperty('SkinHelper.MovieSet.Duration.Minutes')
        WINDOW.clearProperty('SkinHelper.MovieSet.Writer')
        WINDOW.clearProperty('SkinHelper.MovieSet.Director')
        WINDOW.clearProperty('SkinHelper.MovieSet.Genre')
        WINDOW.clearProperty('SkinHelper.MovieSet.Country')
        WINDOW.clearProperty('SkinHelper.MovieSet.Studio')
        WINDOW.clearProperty('SkinHelper.MovieSet.Years')
        WINDOW.clearProperty('SkinHelper.MovieSet.Year')
        WINDOW.clearProperty('SkinHelper.MovieSet.Count')
        WINDOW.clearProperty('SkinHelper.MovieSet.Plot')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesRating')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesAudienceRating')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesConsensus')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesAwards')
        WINDOW.clearProperty('SkinHelper.RottenTomatoesBoxOffice')
        totalNodes = 50
        for i in range(totalNodes):
            if not WINDOW.getProperty('SkinHelper.MovieSet.' + str(i) + '.Title'):
                break
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.Title')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.FanArt')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.Poster')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.Landscape')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.DiscArt')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.ClearLogo')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.ClearArt')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.Banner')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.Rating')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.Resolution')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.Resolution.Type')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.AspectRatio')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.Codec')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.AudioCodec')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.AudioChannels')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.AudioLanguage')
            WINDOW.clearProperty('SkinHelper.MovieSet.' + str(i) + '.Subtitle')
    
    def setMovieSetDetails(self):
        #get movie set details -- thanks to phil65 - used this idea from his skin info script     
        if xbmc.getCondVisibility("SubString(ListItem.Path,videodb://movies/sets/,left)"):
            dbId = xbmc.getInfoLabel("ListItem.DBID")   
            if dbId:
                #try to get from cache first
                if self.moviesetCache.has_key(dbId):
                    json_response = self.moviesetCache[dbId]
                else:
                    json_response = getJSON('VideoLibrary.GetMovieSetDetails', '{"setid": %s, "properties": [ "thumbnail" ], "movies": { "properties":  [ "rating", "art", "file", "year", "director", "writer", "playcount", "genre" , "thumbnail", "runtime", "studio", "plotoutline", "plot", "country", "streamdetails"], "sort": { "order": "ascending",  "method": "year" }} }' % dbId)
                    #save to cache
                    self.moviesetCache[dbId] = json_response
                if json_response:
                    count = 0
                    unwatchedcount = 0
                    watchedcount = 0
                    runtime = 0
                    runtime_mins = 0
                    writer = []
                    director = []
                    genre = []
                    country = []
                    studio = []
                    years = []
                    plot = ""
                    title_list = ""
                    title_header = "[B]" + str(json_response['limits']['total']) + " " + xbmc.getLocalizedString(20342) + "[/B][CR]"
                    set_fanart = []
                    for item in json_response['movies']:
                        
                        if item["playcount"] == 0:
                            unwatchedcount += 1
                        else:
                            watchedcount += 1
                        
                        art = item['art']
                        set_fanart.append(art.get('fanart', ''))
                        WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.Title',item['label'])
                        WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.Poster',art.get('poster', ''))
                        WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.FanArt',art.get('fanart', ''))
                        WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.Landscape',art.get('landscape', ''))
                        WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.DiscArt',art.get('discart', ''))
                        WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.ClearLogo',art.get('clearlogo', ''))
                        WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.ClearArt',art.get('clearart', ''))
                        WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.Banner',art.get('banner', ''))
                        WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.Rating',str(item.get('rating', '')))
                        if item.get('streamdetails',''):
                            streamdetails = item["streamdetails"]
                            audiostreams = streamdetails.get('audio',[])
                            videostreams = streamdetails.get('video',[])
                            subtitles = streamdetails.get('subtitle',[])
                            if len(videostreams) > 0:
                                stream = videostreams[0]
                                height = stream.get("height","")
                                width = stream.get("width","")
                                if height and width:
                                    resolution = ""
                                    if width <= 720 and height <= 480: resolution = "480"
                                    elif width <= 768 and height <= 576: resolution = "576"
                                    elif width <= 960 and height <= 544: resolution = "540"
                                    elif width <= 1280 and height <= 720: resolution = "720"
                                    elif width <= 1920 and height <= 1080: resolution = "1080"
                                    elif width * height >= 6000000: resolution = "4K"
                                    WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.Resolution',resolution)
                                if stream.get("codec",""):
                                    WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.Codec',str(stream["codec"]))    
                                if stream.get("aspect",""):
                                    WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.AspectRatio',str(round(stream["aspect"], 2)))
                            if len(audiostreams) > 0:
                                #grab details of first audio stream
                                stream = audiostreams[0]
                                WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.AudioCodec',stream.get('codec',''))
                                WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.AudioChannels',str(stream.get('channels','')))
                                WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.AudioLanguage',stream.get('language',''))
                            if len(subtitles) > 0:
                                #grab details of first subtitle
                                WINDOW.setProperty('SkinHelper.MovieSet.' + str(count) + '.SubTitle',subtitles[0].get('language',''))

                        title_list += item['label'] + " (" + str(item['year']) + ")[CR]"
                        if item['plotoutline']:
                            plot += "[B]" + item['label'] + " (" + str(item['year']) + ")[/B][CR]" + item['plotoutline'] + "[CR][CR]"
                        else:
                            plot += "[B]" + item['label'] + " (" + str(item['year']) + ")[/B][CR]" + item['plot'] + "[CR][CR]"
                        runtime += item['runtime']
                        count += 1
                        if item.get("writer"):
                            writer += [w for w in item["writer"] if w and w not in writer]
                        if item.get("director"):
                            director += [d for d in item["director"] if d and d not in director]
                        if item.get("genre"):
                            genre += [g for g in item["genre"] if g and g not in genre]
                        if item.get("country"):
                            country += [c for c in item["country"] if c and c not in country]
                        if item.get("studio"):
                            studio += [s for s in item["studio"] if s and s not in studio]
                        years.append(str(item['year']))
                    WINDOW.setProperty('SkinHelper.MovieSet.Plot', plot)
                    if json_response['limits']['total'] > 1:
                        WINDOW.setProperty('SkinHelper.MovieSet.ExtendedPlot', title_header + title_list + "[CR]" + plot)
                    else:
                        WINDOW.setProperty('SkinHelper.MovieSet.ExtendedPlot', plot)
                    WINDOW.setProperty('SkinHelper.MovieSet.Title', title_list)
                    WINDOW.setProperty('SkinHelper.MovieSet.Runtime', str(runtime / 60))
                    self.setDuration(str(runtime / 60))
                    durationString = self.getDurationString(runtime / 60)
                    if durationString:
                        WINDOW.setProperty('SkinHelper.MovieSet.Duration', durationString[2])
                        WINDOW.setProperty('SkinHelper.MovieSet.Duration.Hours', durationString[0])
                        WINDOW.setProperty('SkinHelper.MovieSet.Duration.Minutes', durationString[1])
                    WINDOW.setProperty('SkinHelper.MovieSet.Writer', " / ".join(writer))
                    WINDOW.setProperty('SkinHelper.MovieSet.Director', " / ".join(director))
                    self.setDirector(" / ".join(director))
                    WINDOW.setProperty('SkinHelper.MovieSet.Genre', " / ".join(genre))
                    self.setGenre(" / ".join(genre))
                    WINDOW.setProperty('SkinHelper.MovieSet.Country', " / ".join(country))
                    studioString = " / ".join(studio)
                    WINDOW.setProperty('SkinHelper.MovieSet.Studio', studioString)
                    self.setStudioLogo(studioString)
                   
                    WINDOW.setProperty('SkinHelper.MovieSet.Years', " / ".join(years))
                    WINDOW.setProperty('SkinHelper.MovieSet.Year', years[0] + " - " + years[-1])
                    WINDOW.setProperty('SkinHelper.MovieSet.Count', str(json_response['limits']['total']))
                    WINDOW.setProperty('SkinHelper.MovieSet.WatchedCount', str(watchedcount))
                    WINDOW.setProperty('SkinHelper.MovieSet.UnWatchedCount', str(unwatchedcount))
                    
                    #rotate fanart from movies in set while listitem is in focus
                    if xbmc.getCondVisibility("Skin.HasSetting(SkinHelper.EnableExtraFanart)"):
                        fanartcount = 5
                        delaycount = 5
                        backgroundDelayStr = xbmc.getInfoLabel("skin.string(extrafanartdelay)")
                        if backgroundDelayStr:
                            fanartcount = int(backgroundDelayStr)
                            delaycount = int(backgroundDelayStr)
                        while dbId == xbmc.getInfoLabel("ListItem.DBID") and set_fanart != []:
                            
                            if fanartcount == delaycount:
                                random.shuffle(set_fanart)
                                WINDOW.setProperty('SkinHelper.ExtraFanArtPath', set_fanart[0])
                                fanartcount = 0
                            else:
                                xbmc.sleep(1000)
                                fanartcount += 1

    def setAddonName(self):
        # set addon name as property
        if not xbmc.Player().isPlayingAudio():
            if (xbmc.getCondVisibility("Container.Content(plugins) | !IsEmpty(Container.PluginName)")):
                AddonName = xbmc.getInfoLabel('Container.PluginName').decode('utf-8')
                AddonName = xbmcaddon.Addon(AddonName).getAddonInfo('name')
                WINDOW.setProperty("SkinHelper.Player.AddonName", AddonName)
            else:
                WINDOW.clearProperty("SkinHelper.Player.AddonName")
    
    def setGenre(self, genre=None):

        totalNodes = 10
        for i in range(totalNodes):
            if not WINDOW.getProperty('SkinHelper.ListItemGenre.' + str(i)):
                break
            WINDOW.clearProperty('SkinHelper.ListItemGenre.' + str(i))

        if not genre:
            genre = xbmc.getInfoLabel('ListItem.Genre').decode('utf-8')
        
        genres = []
        if "/" in genre:
            genres = genre.split(" / ")
        else:
            genres.append(genre)
        
        WINDOW.setProperty('SkinHelper.ListItemGenres', "[CR]".join(genres))

        count = 0
        for genre in genres:
            WINDOW.setProperty("SkinHelper.ListItemGenre." + str(count),genre)
            count +=1
    
    def setDirector(self, director=None):
        if not director:
            director = xbmc.getInfoLabel('ListItem.Director').decode('utf-8')
        
        directors = []
        if "/" in director:
            directors = director.split(" / ")
        else:
            directors.append(director)
        
        WINDOW.setProperty('SkinHelper.ListItemDirectors', "[CR]".join(directors))
       
    def setPVRThumbs(self):
        thumb = None

        title = xbmc.getInfoLabel("ListItem.Title").decode('utf-8')
        channel = xbmc.getInfoLabel("ListItem.ChannelName").decode('utf-8')
        
        if xbmc.getCondVisibility("ListItem.IsFolder") and not channel and not title:
            #assume grouped recordings folderPath
            title = xbmc.getInfoLabel("ListItem.Label").decode('utf-8')

        if not xbmc.getCondVisibility("Skin.HasSetting(SkinHelper.EnablePVRThumbs)") or not title:
            return
        
        dbID = title + channel
        
        if channel:
            logo = searchChannelLogo(channel)
            WINDOW.setProperty("SkinHelper.PVR.ChannelLogo",logo)
            
        logMsg("setPVRThumb dbID--> " + dbID)

        if xbmc.getInfoLabel("ListItem.Label").decode('utf-8') == "..":
            return
        
        thumb,fanart,poster,logo = getPVRThumbs(self.pvrArtCache, title, channel)
        
        if thumb:
            WINDOW.setProperty("SkinHelper.PVR.Thumb",thumb)
            self.pvrArtCache[dbID + "SkinHelper.PVR.Thumb"] = thumb
        if fanart:
            WINDOW.setProperty("SkinHelper.PVR.FanArt",fanart)
            self.pvrArtCache[dbID + "SkinHelper.PVR.FanArt"] = fanart
        if logo and channel:
            WINDOW.setProperty("SkinHelper.PVR.ChannelLogo",logo)
            self.pvrArtCache[channel + "SkinHelper.PVR.ChannelLogo"] = logo
        if poster:
            WINDOW.setProperty("SkinHelper.PVR.Poster",poster)
            self.pvrArtCache[dbID + "SkinHelper.PVR.Poster"] = poster
     
    def setStudioLogo(self, studio=None):
        
        if xbmc.getCondVisibility("Container.Content(studios)"):
            studio = self.liLabel
        
        if not studio:
            studio = xbmc.getInfoLabel('ListItem.Studio').decode('utf-8')
        studiologo = None
        studiologoColor = None
        
        studios = []
        if "/" in studio:
            studios = studio.split(" / ")
            WINDOW.setProperty("SkinHelper.ListItemStudio", studios[0])
        else:
            studios.append(studio)
            WINDOW.setProperty("SkinHelper.ListItemStudio", studio)
        
        for studio in studios:
            studio = studio.lower()
            #find logo normal
            if self.allStudioLogos.has_key(studio):
                studiologo = self.allStudioLogos[studio]
            if self.allStudioLogosColor.has_key(studio):
                studiologoColor = self.allStudioLogosColor[studio]    
            
            if not studiologo and not studiologoColor:
                #find logo by substituting characters
                if " (" in studio:
                    studio = studio.split(" (")[0]
                    if self.allStudioLogos.has_key(studio):
                        studiologo = self.allStudioLogos[studio]
                    if self.allStudioLogosColor.has_key(studio):
                        studiologoColor = self.allStudioLogosColor[studio]
            
            if not studiologo and not studiologoColor:
                #find logo by substituting characters for pvr channels
                if " HD" in studio:
                    studio = studio.replace(" HD","")
                elif " " in studio:
                    studio = studio.replace(" ","")
                if self.allStudioLogos.has_key(studio):
                    studiologo = self.allStudioLogos[studio]
                if self.allStudioLogosColor.has_key(studio):
                    studiologoColor = self.allStudioLogosColor[studio]  
        
        if studiologo:
            WINDOW.setProperty("SkinHelper.ListItemStudioLogo", studiologo)
        else:
            WINDOW.clearProperty("SkinHelper.ListItemStudioLogo")
        
        if studiologoColor:
            WINDOW.setProperty("SkinHelper.ListItemStudioLogoColor", studiologo)
        else:
            WINDOW.clearProperty("SkinHelper.ListItemStudioLogoColor")
        
        #set formatted studio logo
        WINDOW.setProperty('SkinHelper.ListItemStudios', "[CR]".join(studios))
        return studiologo
                
    def getStudioLogos(self):
        #fill list with all studio logos
        allLogos = {}
        allLogosColor = {}
        allPaths = []
        allPathsColor = []

        CustomStudioImagesPath = xbmc.getInfoLabel("Skin.String(SkinHelper.CustomStudioImagesPath)").decode('utf-8')
        if CustomStudioImagesPath + xbmc.getSkinDir() != self.LastCustomStudioImagesPath:
            #only proceed if the custom path or skin has changed...
            self.LastCustomStudioImagesPath = CustomStudioImagesPath + xbmc.getSkinDir()
            
            #add the custom path to the list
            if CustomStudioImagesPath:
                path = CustomStudioImagesPath
                if not (CustomStudioImagesPath.endswith("/") or CustomStudioImagesPath.endswith("\\")):
                    CustomStudioImagesPath = CustomStudioImagesPath + os.sep()
                    allPaths.append(CustomStudioImagesPath)
            
            #add skin provided paths
            allPaths.append("special://skin/extras/flags/studios/")
            allPathsColor.append("special://skin/extras/flags/studioscolor/")
            
            #add images provided by the image resource addons
            allPaths.append("resource://resource.images.studios.white/")
            allPathsColor.append("resource://resource.images.studios.coloured/")
            allPaths.append("special://home/addons/resource.images.studios.white/")
            allPathsColor.append("special://home/addons/resource.images.studios.coloured/")
            
            #check all white logos
            for path in allPaths:               
                if xbmcvfs.exists(path):
                    dirs, files = xbmcvfs.listdir(path)
                    for file in files:
                        name = file.split(".")[0].lower()
                        if not allLogos.has_key(name):
                            allLogos[name] = path + file
                    for dir in dirs:
                        dirs2, files2 = xbmcvfs.listdir(os.path.join(path,dir))
                        for file in files2:
                            name = dir + "/" + file.split(".")[0].lower()
                            if not allLogos.has_key(name):
                                if "/" in path:
                                    sep = "/"
                                else:
                                    sep = "\\"
                                allLogos[name] = path + dir + sep + file
                    
            #check all color logos
            for path in allPathsColor:
                if xbmcvfs.exists(path):
                    dirs, files = xbmcvfs.listdir(path)
                    for file in files:
                        name = file.split(".")[0].lower()
                        if not allLogos.has_key(name):
                            allLogos[name] = path + file
                    for dir in dirs:
                        dirs2, files2 = xbmcvfs.listdir(os.path.join(path,dir))
                        for file in files2:
                            name = dir + "/" + file.split(".")[0].lower()
                            if not allLogos.has_key(name):
                                if "/" in path:
                                    sep = "/"
                                else:
                                    sep = "\\"
                                allLogos[name] = path + dir + sep + file
            
            #assign all found logos in the list
            self.allStudioLogos = allLogos
            self.allStudioLogosColor = allLogosColor
    
    def setDuration(self,currentDuration=None):
        if not currentDuration:
            currentDuration = xbmc.getInfoLabel("ListItem.Duration")
        
        if ":" in currentDuration:
            durLst = currentDuration.split(":")
            if len(durLst) == 1:
                currentDuration = "0"
            elif len(durLst) == 2:
                currentDuration = durLst[0]
            elif len(durLst) == 3:
                currentDuration = str((int(durLst[0])*60) + int(durLst[1]))
                
        # monitor listitem to set duration
        if currentDuration:
            durationString = self.getDurationString(currentDuration)
            if durationString:
                WINDOW.setProperty('SkinHelper.ListItemDuration', durationString[2])
                WINDOW.setProperty('SkinHelper.ListItemDuration.Hours', durationString[0])
                WINDOW.setProperty('SkinHelper.ListItemDuration.Minutes', durationString[1])
            else:
                WINDOW.clearProperty('SkinHelper.ListItemDuration')
                WINDOW.clearProperty('SkinHelper.ListItemDuration.Hours')
                WINDOW.clearProperty('SkinHelper.ListItemDuration.Minutes')
        else:
            WINDOW.clearProperty('SkinHelper.ListItemDuration')
            WINDOW.clearProperty('SkinHelper.ListItemDuration.Hours')
            WINDOW.clearProperty('SkinHelper.ListItemDuration.Minutes')
        
    def getDurationString(self, duration):
        if duration == None or duration == 0:
            return None
        try:
            full_minutes = int(duration)
            minutes = str(full_minutes % 60)
            minutes = str(minutes).zfill(2)
            hours   = str(full_minutes // 60)
            durationString = hours + ':' + minutes
        except Exception as e:
            logMsg("ERROR in getDurationString ! --> " + str(e), 0)
            return None
        return ( hours, minutes, durationString )
              
    def checkMusicArt(self,widget=None):
        cacheFound = False
        cdArt = None
        LogoArt = None
        BannerArt = None
        extraFanArt = None
        Info = None
        TrackList = ""
        
        if widget:
            dbID = widget
        else:
            dbID = xbmc.getInfoLabel("ListItem.Artist").decode('utf-8') + xbmc.getInfoLabel("ListItem.Album").decode('utf-8')
        
        if dbID and self.lastMusicDbId == dbID:
            return
        
        logMsg("checkMusicArt dbID--> " + dbID)

        self.lastMusicDbId = dbID
        
        if not widget and (self.liLabel == ".." or not xbmc.getInfoLabel("ListItem.FolderPath").decode('utf-8').startswith("musicdb") or not dbID):
            WINDOW.setProperty("SkinHelper.ExtraFanArtPath","") 
            WINDOW.clearProperty("SkinHelper.Music.BannerArt") 
            WINDOW.clearProperty("SkinHelper.Music.LogoArt") 
            WINDOW.clearProperty("SkinHelper.Music.DiscArt")
            WINDOW.clearProperty("SkinHelper.Music.Info")
            WINDOW.clearProperty("SkinHelper.Music.TrackList")
            return
        
        #get the items from cache first
        if self.musicArtCache.has_key(dbID + "SkinHelper.Music.DiscArt"):
            cacheFound = True
            cdArt = self.musicArtCache[dbID + "SkinHelper.Music.DiscArt"]            

        if self.musicArtCache.has_key(dbID + "SkinHelper.Music.LogoArt"):
            cacheFound = True
            LogoArt = self.musicArtCache[dbID + "SkinHelper.Music.LogoArt"]
                
        if self.musicArtCache.has_key(dbID + "SkinHelper.Music.BannerArt"):
            cacheFound = True
            BannerArt = self.musicArtCache[dbID + "SkinHelper.Music.BannerArt"]
        
        if self.musicArtCache.has_key(dbID + "extraFanArt"):
            cacheFound = True
            extraFanArt = self.musicArtCache[dbID + "extraFanArt"]
                
        if self.musicArtCache.has_key(dbID + "SkinHelper.Music.Info"):
            cacheFound = True
            Info = self.musicArtCache[dbID + "SkinHelper.Music.Info"]
        
        if self.musicArtCache.has_key(dbID + "SkinHelper.Music.TrackList"):
            cacheFound = True
            TrackList = self.musicArtCache[dbID + "SkinHelper.Music.TrackList"]

        if not cacheFound and not widget:
            logMsg("checkMusicArt no cache found for dbID--> " + dbID)
            path = None
            json_response = None
            folderPath = xbmc.getInfoLabel("ListItem.FolderPath").decode('utf-8')
            dbid = xbmc.getInfoLabel("ListItem.DBID")
            cdArt, LogoArt, BannerArt, extraFanArt, Info, TrackList = getMusicArtByDbId(dbid, self.contentType)
      
            self.musicArtCache[dbID + "extraFanArt"] = extraFanArt
            self.musicArtCache[dbID + "SkinHelper.Music.DiscArt"] = cdArt
            self.musicArtCache[dbID + "SkinHelper.Music.BannerArt"] = BannerArt
            self.musicArtCache[dbID + "SkinHelper.Music.LogoArt"] = LogoArt
            self.musicArtCache[dbID + "SkinHelper.Music.TrackList"] = TrackList
            self.musicArtCache[dbID + "SkinHelper.Music.Info"] = Info

        #set properties
        WINDOW.setProperty("SkinHelper.ExtraFanArtPath",extraFanArt)
        WINDOW.setProperty("SkinHelper.Music.DiscArt",cdArt)
        WINDOW.setProperty("SkinHelper.Music.BannerArt",BannerArt)       
        WINDOW.setProperty("SkinHelper.Music.LogoArt",LogoArt)
        WINDOW.setProperty("SkinHelper.Music.TrackList",TrackList)
        WINDOW.setProperty("SkinHelper.Music.Info",Info)
              
    def setStreamDetails(self):
        streamdetails = None
        #clear props first
        WINDOW.clearProperty('SkinHelper.ListItemSubtitles')
        WINDOW.clearProperty('SkinHelper.ListItemAllAudioStreams')
        totalNodes = 50
        for i in range(totalNodes):
            if not WINDOW.getProperty('SkinHelper.ListItemAudioStreams.%d.AudioCodec' % i):
                break
            WINDOW.clearProperty('SkinHelper.ListItemAudioStreams.%d.Language' % i)
            WINDOW.clearProperty('SkinHelper.ListItemAudioStreams.%d.AudioCodec' % i)
            WINDOW.clearProperty('SkinHelper.ListItemAudioStreams.%d.AudioChannels' % i)
            WINDOW.clearProperty('SkinHelper.ListItemAudioStreams.%d'%i)
        
        contenttype = getCurrentContentType()
        dbId = xbmc.getInfoLabel("ListItem.DBID")
        if not dbId or dbId == "-1":
            return
        
        if self.streamdetailsCache.has_key(contenttype+dbId):
            #get data from cache
            streamdetails = self.streamdetailsCache[contenttype+dbId]
        else:
            streamdetails = None
            json_result = {}
            # get data from json
            if contenttype == "movies" and dbId:
                json_result = getJSON('VideoLibrary.GetMovieDetails', '{ "movieid": %d, "properties": [ "title", "streamdetails" ] }' %int(dbId))
            elif contenttype == "episodes" and dbId:
                json_result = getJSON('VideoLibrary.GetEpisodeDetails', '{ "episodeid": %d, "properties": [ "title", "streamdetails" ] }' %int(dbId))
            elif contenttype == "musicvideos" and dbId:
                json_result = getJSON('VideoLibrary.GetMusicVideoDetails', '{ "musicvideoid": %d, "properties": [ "title", "streamdetails" ] }' %int(dbId))       
            if json_result.has_key("streamdetails"): 
                streamdetails = json_result["streamdetails"]
            self.streamdetailsCache[contenttype+dbId] = streamdetails
        
        if streamdetails:
            audio = streamdetails['audio']
            subtitles = streamdetails['subtitle']
            allAudio = []
            allAudioStr = []
            allSubs = []
            count = 0
            for item in audio:
                if str(item['language']) not in allAudio:
                    allAudio.append(str(item['language']))
                    codec = item['codec']
                    channels = item['channels']
                    if "ac3" in codec: codec = "Dolby D"
                    elif "dca" in codec: codec = "DTS"
                    elif "dts-hd" in codec or "dtshd" in codec: codec = "DTS HD"
                    
                    if channels == 1: channels = "1.0"
                    elif channels == 2: channels = "2.0"
                    elif channels == 3: channels = "2.1"
                    elif channels == 4: channels = "4.0"
                    elif channels == 5: channels = "5.0"
                    elif channels == 6: channels = "5.1"
                    elif channels == 7: channels = "6.1"
                    elif channels == 8: channels = "7.1"
                    elif channels == 9: channels = "8.1"
                    elif channels == 10: channels = "9.1"
                    else: channels = str(channels)
                    language = item['language']
                    if not language: language = "?"
                    WINDOW.setProperty('SkinHelper.ListItemAudioStreams.%d.Language' % count, item['language'])
                    WINDOW.setProperty('SkinHelper.ListItemAudioStreams.%d.AudioCodec' % count, item['codec'])
                    WINDOW.setProperty('SkinHelper.ListItemAudioStreams.%d.AudioChannels' % count, str(item['channels']))
                    sep = "•".decode('utf-8')
                    audioStr = '%s %s %s %s %s' %(language,sep,codec,sep,channels)
                    WINDOW.setProperty('SkinHelper.ListItemAudioStreams.%d'%count, audioStr)
                    allAudioStr.append(audioStr)
                    count += 1
            count = 0
            for item in subtitles:
                if str(item['language']) not in allSubs:
                    allSubs.append(str(item['language']))
                    WINDOW.setProperty('SkinHelper.ListItemSubtitles.%d' % count, item['language'])
                    count += 1
            WINDOW.setProperty('SkinHelper.ListItemSubtitles', " / ".join(allSubs))
            WINDOW.setProperty('SkinHelper.ListItemAllAudioStreams', " / ".join(allAudioStr))
      
    def setForcedView(self):
        currentForcedView = xbmc.getInfoLabel("Skin.String(SkinHelper.ForcedViews.%s)" %self.contentType)
        if self.contentType and currentForcedView and currentForcedView != "None" and xbmc.getCondVisibility("Skin.HasSetting(SkinHelper.ForcedViews.Enabled)"):
            WINDOW.setProperty("SkinHelper.ForcedView",currentForcedView)
            xbmc.executebuiltin("Container.SetViewMode(%s)" %currentForcedView)
            if not xbmc.getCondVisibility("Control.HasFocus(%s)" %currentForcedView):
                xbmc.sleep(100)
                xbmc.executebuiltin("Container.SetViewMode(%s)" %currentForcedView)
                xbmc.executebuiltin("SetFocus(%s)" %currentForcedView)
        else:
            WINDOW.clearProperty("SkinHelper.ForcedView")
        
    def checkExtraFanArt(self):
        
        lastPath = None
        efaPath = None
        efaFound = False
        liArt = None
        
        if xbmc.getCondVisibility("Window.IsActive(movieinformation)"):
            return
        
        #always clear the individual fanart items first
        totalNodes = 50
        for i in range(totalNodes):
            if not WINDOW.getProperty('SkinHelper.ExtraFanArt.' + str(i)):
                break
            WINDOW.clearProperty('SkinHelper.ExtraFanArt.' + str(i))
        
        #get the item from cache first
        if self.extraFanartCache.has_key(self.liPath):
            if self.extraFanartCache[self.liPath][0] == "None":
                WINDOW.setProperty("SkinHelper.ExtraFanArtPath","")
                return
            else:
                WINDOW.setProperty("SkinHelper.ExtraFanArtPath",self.extraFanartCache[self.liPath][0])
                count = 0
                for file in self.extraFanartCache[self.liPath][1]:
                    WINDOW.setProperty("SkinHelper.ExtraFanArt." + str(count),file)
                    count +=1  
                return
        
        if not xbmc.getCondVisibility("Skin.HasSetting(SkinHelper.EnableExtraFanart)"):
            WINDOW.setProperty("SkinHelper.ExtraFanArtPath","")
            return
        
        if (self.liPath != None and self.liPath != self.liPathLast and (xbmc.getCondVisibility("Container.Content(movies) | Container.Content(seasons) | Container.Content(episodes) | Container.Content(tvshows)")) and not "videodb:" in self.liPath):
                           
            if xbmc.getCondVisibility("Container.Content(episodes)"):
                liArt = xbmc.getInfoLabel("ListItem.Art(tvshow.fanart)").decode('utf-8')
            
            # do not set extra fanart for virtuals
            if (("plugin://" in self.liPath) or ("addon://" in self.liPath) or ("sources" in self.liPath) or ("plugin://" in self.folderPath) or ("sources://" in self.folderPath) or ("plugin://" in self.folderPath)):
                WINDOW.setProperty("SkinHelper.ExtraFanArtPath","")
                self.extraFanartCache[self.liPath] = "None"
            else:

                if xbmcvfs.exists(self.liPath + "extrafanart/"):
                    efaPath = self.liPath + "extrafanart/"
                else:
                    pPath = self.liPath.rpartition("/")[0]
                    pPath = pPath.rpartition("/")[0]
                    if xbmcvfs.exists(pPath + "/extrafanart/"):
                        efaPath = pPath + "/extrafanart/"
                        
                if xbmcvfs.exists(efaPath):
                    dirs, files = xbmcvfs.listdir(efaPath)
                    count = 0
                    extraFanArtfiles = []
                    for file in files:
                        if file.lower().endswith(".jpg"):
                            efaFound = True
                            WINDOW.setProperty("SkinHelper.ExtraFanArt." + str(count),efaPath+file)
                            extraFanArtfiles.append(efaPath+file)
                            count +=1  
       
                if (efaPath != None and efaFound == True):
                    WINDOW.setProperty("SkinHelper.ExtraFanArtPath",efaPath)
                    self.extraFanartCache[self.liPath] = [efaPath, extraFanArtfiles]     
                else:
                    WINDOW.setProperty("SkinHelper.ExtraFanArtPath","")
                    self.extraFanartCache[self.liPath] = ["None",[]]
        else:
            WINDOW.setProperty("SkinHelper.ExtraFanArtPath","")

    def setRottenRatings(self):
        imdbnumber = xbmc.getInfoLabel("ListItem.IMDBNumber")
        if (self.contentType == "movies" or self.contentType=="setmovies") and imdbnumber:
            if self.rottenCache.has_key(imdbnumber):
                #get data from cache
                result = self.rottenCache[imdbnumber]
            elif not WINDOW.getProperty("SkinHelper.DisableInternetLookups"):
                url = 'http://www.omdbapi.com/?i=%s&plot=short&tomatoes=true&r=json' %imdbnumber
                res = requests.get(url)
                result = json.loads(res.content.decode('utf-8','replace'))
                if result:
                    self.rottenCache[imdbnumber] = result
            if result:
                criticsscore = result.get('tomatoMeter',"")
                criticconsensus = result.get('tomatoConsensus',"")
                audiencescore = result.get('Metascore',"")
                awards = result.get('Awards',"")
                boxoffice = result.get('BoxOffice',"")
                if criticsscore:
                    WINDOW.setProperty("SkinHelper.RottenTomatoesRating",criticsscore)
                if audiencescore:
                    WINDOW.setProperty("SkinHelper.RottenTomatoesAudienceRating",audiencescore)
                if criticconsensus:
                    WINDOW.setProperty("SkinHelper.RottenTomatoesConsensus",criticconsensus)
                if awards:
                    WINDOW.setProperty("SkinHelper.RottenTomatoesAwards",awards)
                if boxoffice:
                    WINDOW.setProperty("SkinHelper.RottenTomatoesBoxOffice",boxoffice)

    def focusEpisode(self):
        # monitor episodes for auto focus first unwatched - Helix only as it is included in Kodi as of Isengard by default
        if xbmc.getCondVisibility("Skin.HasSetting(AutoFocusUnwatchedEpisode)"):
            
            #store unwatched episodes
            if ((xbmc.getCondVisibility("Container.Content(seasons) | Container.Content(tvshows)")) and xbmc.getCondVisibility("!IsEmpty(ListItem.Property(UnWatchedEpisodes))")):
                try:
                    self.unwatched = int(xbmc.getInfoLabel("ListItem.Property(UnWatchedEpisodes)"))
                except: pass
            
            if (xbmc.getCondVisibility("Container.Content(episodes) | Container.Content(seasons)")):
                
                if self.unwatched != 0:
                    totalItems = 0
                    curView = xbmc.getInfoLabel("Container.Viewmode") 
                    
                    # get all views from views-file
                    viewId = None
                    skin_view_file = os.path.join(xbmc.translatePath('special://skin/extras'), "views.xml")
                    tree = etree.parse(skin_view_file)
                    root = tree.getroot()
                    for view in root.findall('view'):
                        if curView == xbmc.getLocalizedString(int(view.attrib['languageid'])):
                            viewId=view.attrib['value']
                    
                    wid = xbmcgui.getCurrentWindowId()
                    window = xbmcgui.Window( wid )        
                    control = window.getControl(int(viewId))
                    totalItems = int(xbmc.getInfoLabel("Container.NumItems"))
                    
                    if (xbmc.getCondVisibility("Container.SortDirection(ascending)")):
                        curItem = 0
                        while ((xbmc.getCondVisibility("Container.Content(episodes) | Container.Content(seasons)")) and totalItems >= curItem):
                            if (xbmc.getInfoLabel("Container.ListItem(" + str(curItem) + ").Overlay") != "OverlayWatched.png" and xbmc.getInfoLabel("Container.ListItem(" + str(curItem) + ").Label") != ".." and not xbmc.getInfoLabel("Container.ListItem(" + str(curItem) + ").Label").startswith("*")):
                                if curItem != 0:
                                    #control.selectItem(curItem)
                                    xbmc.executebuiltin("Control.Move(%s,%s)" %(str(viewId),str(curItem)))
                                break
                            else:
                                curItem += 1
                    
                    elif (xbmc.getCondVisibility("Container.SortDirection(descending)")):
                        curItem = totalItems
                        while ((xbmc.getCondVisibility("Container.Content(episodes) | Container.Content(seasons)")) and curItem != 0):
                            
                            if (xbmc.getInfoLabel("Container.ListItem(" + str(curItem) + ").Overlay") != "OverlayWatched.png"):
                                xbmc.executebuiltin("Control.Move(%s,%s)" %(str(viewId),str(curItem)))
                                break
                            else:    
                                curItem -= 1
           