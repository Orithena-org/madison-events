from .isthmus import IsthmusScraper
from .eventbrite import EventbriteScraper
# OvertureScraper disabled: overture.org redirects through a session/ticket system
# that requires JS rendering and cookie handling. Returns 0 events consistently.
# Re-enable if Playwright or a headless browser is added to the pipeline.
# from .overture import OvertureScraper
from .uw_madison import UWMadisonScraper
from .city_madison import CityMadisonScraper
from .patch import PatchScraper
from .visitmadison import VisitMadisonScraper

ALL_SCRAPERS = [IsthmusScraper, EventbriteScraper, UWMadisonScraper, CityMadisonScraper, PatchScraper, VisitMadisonScraper]
