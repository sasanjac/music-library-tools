import pathlib
from collections import Counter
from dataclasses import dataclass

from loguru import logger
from plexapi import audio as paud
from plexapi import server as pserv

from music_library_tools import utils


@dataclass
class PlexDaemon:
    plex_url: str
    token: str
    base_path: str

    def __post_init__(self) -> None:
        self.server = pserv.PlexServer(self.plex_url, self.token)
        self.collection = self.server.library.sectionByID(7)

    def check_and_fix_duplicates(self) -> None:
        albums = self.collection.albums()
        album_titles = [a.title for a in albums]
        y = Counter(album_titles)
        duplicates = [k for k, v in y.items() if v > 1]
        for d in duplicates:
            dalbs = [a for a in albums if a.title == d]
            if len(dalbs) > 2:
                logger.warning(f"Album {d} consists of more than 2 parts. Check manually!")
                break
            alb1, alb2 = dalbs
            if self.tracks_equal(alb1, alb2):
                logger.info(f"Copying info for {alb1.title}")
                self.copy_alb_info(alb1, alb2)
            else:
                logger.info(f"Merging {alb1.title}")
                self.merge(alb1, alb2)

    def update_labels(self) -> None:
        albums = self.collection.albums()
        for alb in albums:
            if alb.studio is None:
                plex_path = alb.tracks()[0].media[0].parts[0].file
                real_path = plex_path.replace("/music_el", self.base_path)
                try:
                    x = utils.Audio(pathlib.Path(real_path))
                except utils.AudioError as e:
                    logger.error(e)
                    continue
                try:
                    label = x["label"][0]
                except KeyError:
                    try:
                        label = x["publisher"][0]
                    except KeyError:
                        try:
                            label = x["organization"][0]
                        except KeyError:
                            pass
                logger.info(f"Updating label {label} for album {alb.title}.")
                alb.edit(**{"studio.value": label})

    @staticmethod
    def tracks_equal(alb1: paud.Album, alb2: paud.Album) -> bool:
        a1t = alb1.tracks()
        a2t = alb2.tracks()
        for t1, t2 in zip(a1t, a2t):
            if t1.title != t2.title:
                return False
        return True

    def copy_alb_info(self, alb1: paud.Album, alb2: paud.Album) -> None:
        a1t = alb1.tracks()
        a2t = alb2.tracks()
        for t1, t2 in zip(a1t, a2t):
            t1_main = t1.media[0].container == "flac"
            t2_main = t2.media[0].container == "flac"
            if t1_main == t2_main:
                if t1.addedAt < t2.addedAt:
                    t2.delete()
                else:
                    t1.delete()
            else:
                if t1_main:
                    if t2.userRating is not None:
                        t1.edit(**{"userRating.value": t2.userRating})
                    t2.delete()
                else:
                    if t1.userRating is not None:
                        t2.edit(**{"userRating.value": t1.userRating})
                    t1.delete()

    def merge(self, alb1: paud.Album, alb2: paud.Album) -> bool:
        key = f"{alb1.key}/merge?ids={alb2.ratingKey}"
        return alb1._server.query(key, method=alb1._server._session.put)
