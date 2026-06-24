"""
Bracket Repository — handles data access for tournament brackets and their structure.
"""
from typing import Any, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models.bracket import Bracket
from app.database.models.match import Match
from app.database.models.team import Team


class BracketRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_bracket_by_tournament(self, organization_id: str, tournament_id: str) -> Bracket | None:
        """Fetch the most recent bracket for a tournament."""
        q = (
            select(Bracket)
            .where(Bracket.organization_id == organization_id)
            .where(Bracket.tournament_id == tournament_id)
            .order_by(Bracket.stage.desc())
        )
        result = await self.session.execute(q)
        return result.scalars().first()

    async def get_full_bracket_tree(self, organization_id: str, tournament_id: str) -> dict[str, Any]:
        """
        Constructs a JSON-compatible tree of the tournament bracket.
        This is used by the Web API to render visual brackets.
        """
        bracket = await self.get_bracket_by_tournament(organization_id, tournament_id)
        if not bracket:
            return {"error": "No bracket found for this tournament"}

        # Fetch all matches for this tournament
        match_q = (
            select(Match)
            .where(Match.organization_id == organization_id)
            .where(Match.tournament_id == tournament_id)
            .where(Match.deleted_at.is_(None))
            .order_by(Match.round.asc(), Match.match_number.asc())
        )
        match_result = await self.session.execute(match_q)
        matches = match_result.scalars().all()

        # Fetch all teams to resolve names
        team_ids = set()
        for m in matches:
            if m.team1_id: team_ids.add(m.team1_id)
            if m.team2_id: team_ids.add(m.team2_id)
        
        team_q = select(Team).where(Team.id.in_(list(team_ids)))
        team_result = await self.session.execute(team_q)
        teams_map = {t.id: t.name for t in team_result.scalars().all()}

        # Organize matches by round
        rounds_data = {}
        for m in matches:
            r = m.round or 0
            if r not in rounds_data:
                rounds_data[r] = []
            
            rounds_data[r].append({
                "match_id": m.id,
                "match_number": m.match_number,
                "team1": teams_map.get(m.team1_id, "TBD"),
                "team2": teams_map.get(m.team2_id, "TBD"),
                "score1": m.score_team1,
                "score2": m.score_team2,
                "winner_id": m.winner_id,
                "status": m.status.value,
            })

        return {
            "tournament_id": tournament_id,
            "bracket_id": bracket.id,
            "format": bracket.format if hasattr(bracket, 'format') else "unknown",
            "stage": bracket.stage,
            "rounds": rounds_data,
            "metadata": bracket.bracket_data or {},
        }
