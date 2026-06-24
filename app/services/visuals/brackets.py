"""
Visual Bracket Service — generates image-based tournament brackets.
"""
import logging
from PIL import Image, ImageDraw, ImageFont
import io

logger = logging.getLogger(__name__)


class VisualBracketService:
    # Color Palette
    COLOR_BG = (24, 24, 27)       # Dark Charcoal
    COLOR_MATCH_BOX = (45, 45, 50) # Lighter Grey
    COLOR_TEXT = (240, 240, 240)   # Off-white
    COLOR_ACCENT = (99, 102, 241)  # Indigo
    COLOR_WINNER = (16, 185, 129)  # Emerald

    def __init__(self):
        try:
            self.font = ImageFont.load_default()
        except Exception:
            self.font = ImageFont.load_default()

    async def generate_se_bracket_image(self, tournament_name: str, bracket_data: dict) -> io.BytesIO:
        """
        Generates a visual Single Elimination bracket.
        bracket_data comes from BracketRepository.get_full_bracket_tree.
        """
        rounds = bracket_data.get("rounds", {})
        if not rounds:
            raise ValueError("No bracket data available")

        # Layout constants
        match_width = 180
        match_height = 60
        round_spacing = 250
        vertical_spacing = 100
        
        sorted_rounds = sorted(rounds.keys())
        num_rounds = len(sorted_rounds)
        max_matches = len(rounds[sorted_rounds[0]])
        
        # Image Size
        width = num_rounds * round_spacing + 100
        height = max_matches * vertical_spacing + 200
        
        img = Image.new("RGB", (width, height), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)

        # Draw Tournament Title
        draw.text((20, 20), f"🏆 {tournament_name} - Bracket", fill=self.COLOR_ACCENT, font=self.font)

        # Draw Rounds
        for r_idx, r_num in enumerate(sorted_rounds):
            round_matches = rounds[r_num]
            x_offset = 50 + (r_idx * round_spacing)
            
            for m_idx, match in enumerate(round_matches):
                # Calculate vertical position
                # In SE, matches in round N are spaced based on matches in round N-1
                # Simple linear spacing for this implementation
                y_offset = 80 + (m_idx * vertical_spacing)
                
                # Draw Match Box
                draw.rectangle(
                    [x_offset, y_offset, x_offset + match_width, y_offset + match_height],
                    fill=self.COLOR_MATCH_BOX,
                    outline=self.COLOR_ACCENT
                )
                
                # Draw Teams
                t1 = match["team1"]
                t2 = match["team2"]
                s1 = match["score1"] or 0
                s2 = match["score2"] or 0
                
                # Highlight Winner
                t1_color = self.COLOR_WINNER if match["winner_id"] == match.get("team1_id") else self.COLOR_TEXT
                t2_color = self.COLOR_WINNER if match["winner_id"] == match.get("team2_id") else self.COLOR_TEXT
                
                draw.text((x_offset + 10, y_offset + 10), f"{t1} {s1}", fill=t1_color, font=self.font)
                draw.text((x_offset + 10, y_offset + 30), f"{t2} {s2}", fill=t2_color, font=self.font)
                
                # Draw Connector lines to next round
                if r_idx < num_rounds - 1:
                    next_x = x_offset + round_spacing
                    # Mid-point of current match to mid-point of next match
                    # This is a simplification; real brackets use a tree branching logic
                    next_y = 80 + ((m_idx // 2) * vertical_spacing)
                    draw.line(
                        [x_offset + match_width, y_offset + match_height // 2, next_x, next_y + match_height // 2],
                        fill=self.COLOR_MATCH_BOX,
                        width=2
                    )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
