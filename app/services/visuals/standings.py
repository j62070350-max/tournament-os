"""
Visual Standings Service — generates professional image-based standings tables.
"""
import logging
from PIL import Image, ImageDraw, ImageFont
import io

logger = logging.getLogger(__name__)


class VisualStandingsService:
    # Color Palette
    COLOR_BG = (24, 24, 27)       # Dark Charcoal
    COLOR_HEADER = (45, 45, 50)    # Lighter Grey
    COLOR_TEXT = (240, 240, 240)   # Off-white
    COLOR_ACCENT = (99, 102, 241)  # Indigo
    COLOR_GOLD = (255, 215, 0)     # Gold
    COLOR_SILVER = (192, 192, 192) # Silver
    COLOR_BRONZE = (205, 127, 50)  # Bronze

    def __init__(self):
        # In a real environment, we would load a custom TTF font here.
        # For now, we use the default.
        try:
            self.font_header = ImageFont.load_default()
            self.font_row = ImageFont.load_default()
        except Exception:
            self.font_header = ImageFont.load_default()
            self.font_row = ImageFont.load_default()

    async def generate_standings_image(self, tournament_name: str, standings_data: list[dict]) -> io.BytesIO:
        """
        Generates a visual standings image from a list of team data.
        Each team dict should have: rank, team_name, wins, losses, points.
        """
        # Image Settings
        row_height = 40
        header_height = 60
        width = 600
        height = header_height + (len(standings_data) * row_height) + 20
        
        # Create Image
        img = Image.new("RGB", (width, height), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)

        # Draw Header
        draw.rectangle([0, 0, width, header_height], fill=self.COLOR_HEADER)
        
        # Header Columns
        cols = {
            "Rank": (40, 0),
            "Team": (120, 0),
            "W": (350, 0),
            "L": (400, 0),
            "Pts": (450, 0)
        }
        
        for text, (x, _) in cols.items():
            draw.text((x, 20), text, fill=self.COLOR_TEXT, font=self.font_header)

        # Draw Rows
        for i, s in enumerate(standings_data):
            y = header_height + (i * row_height)
            
            # Highlight Top 3
            rank = s.get("rank", i + 1)
            row_color = self.COLOR_BG
            text_color = self.COLOR_TEXT
            
            if rank == 1: text_color = self.COLOR_GOLD
            elif rank == 2: text_color = self.COLOR_SILVER
            elif rank == 3: text_color = self.COLOR_BRONZE

            # Draw Team Data
            draw.text((cols["Rank"][0], y + 10), str(rank), fill=text_color, font=self.font_row)
            draw.text((cols["Team"][0], y + 10), str(s.get("team_name", "Unknown")), fill=self.COLOR_TEXT, font=self.font_row)
            draw.text((cols["W"][0], y + 10), str(s.get("wins", 0)), fill=self.COLOR_TEXT, font=self.font_row)
            draw.text((cols["L"][0], y + 10), str(s.get("losses", 0)), fill=self.COLOR_TEXT, font=self.font_row)
            draw.text((cols["Pts"][0], y + 10), str(s.get("points", 0)), fill=self.COLOR_TEXT, font=self.font_row)
            
            # Divider line
            draw.line([0, y + row_height, width, y + row_height], fill=(40, 40, 45), width=1)

        # Tournament Title
        draw.text((20, 10), f"🏆 {tournament_name} - Live Standings", fill=self.COLOR_ACCENT, font=self.font_header)

        # Save to Buffer
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
