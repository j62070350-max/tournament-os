"""
Public routes — tournament listings, individual tournament pages.
No auth required.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.repositories.tournament import TournamentRepository
from app.database.models.tournament import TournamentStatus

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/tournaments")
async def list_public_tournaments(
    limit: int = 20, offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    repo = TournamentRepository(session)
    tournaments = await repo.list_public(limit=limit, offset=offset)
    total = await repo.count(organization_id=None) if hasattr(repo, 'count_public') else len(tournaments)
    return {
        "tournaments": [
            {
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "game": t.game,
                "format": t.format.value,
                "status": t.status.value,
                "prize_pool": t.prize_pool,
                "max_teams": t.max_teams,
                "region": t.region,
                "registration_open_at": str(t.registration_open_at or ""),
                "match_start_at": str(t.match_start_at or ""),
            }
            for t in tournaments
        ],
        "total": len(tournaments),
        "has_more": len(tournaments) == limit,
        "limit": limit,
        "offset": offset,
    }


@router.get("/tournaments/{tournament_id}")
async def get_public_tournament(
    tournament_id: str,
    organization_id: str,
    session: AsyncSession = Depends(get_session),
):
    repo = TournamentRepository(session)
    t = await repo.get_by_id(tournament_id, organization_id)
    if not t or t.visibility != "public":
        raise HTTPException(status_code=404, detail="Tournament not found")

    return {
        "id": t.id,
        "name": t.name,
        "slug": t.slug,
        "game": t.game,
        "format": t.format.value,
        "status": t.status.value,
        "description": t.description,
        "rules": t.rules,
        "prize_pool": t.prize_pool,
        "max_teams": t.max_teams,
        "region": t.region,
        "platform": t.platform,
        "registration_open_at": str(t.registration_open_at or ""),
        "registration_close_at": str(t.registration_close_at or ""),
        "checkin_open_at": str(t.checkin_open_at or ""),
        "match_start_at": str(t.match_start_at or ""),
    }


@router.get("/tournaments/{tournament_id}/bracket")
async def get_public_bracket(
    tournament_id: str,
    organization_id: str,
    session: AsyncSession = Depends(get_session),
):
    from app.database.repositories.bracket import BracketRepository
    repo = BracketRepository(session)
    return await repo.get_full_bracket_tree(organization_id, tournament_id)


@router.get("/tournaments/{tournament_id}/matches")
async def get_public_matches(
    tournament_id: str,
    organization_id: str,
    session: AsyncSession = Depends(get_session),
):
    from app.database.repositories.match import MatchRepository
    repo = MatchRepository(session)
    matches = await repo.list_all(organization_id, tournament_id)
    return {
        "matches": [
            {
                "id": m.id,
                "round": m.round,
                "match_number": m.match_number,
                "team1_id": m.team1_id,
                "team2_id": m.team2_id,
                "winner_id": m.winner_id,
                "score1": m.score_team1,
                "score2": m.score_team2,
                "status": m.status.value,
                "scheduled_at": str(m.scheduled_at or ""),
            }
            for m in matches
        ]
    }


@router.get("/tournaments/{tournament_id}/standings")
async def get_public_standings(
    tournament_id: str, organization_id: str,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    from app.database.repositories.standings import StandingsRepository
    from app.database.models.team import Team
    repo = StandingsRepository(session)
    standings = await repo.get_ranked(organization_id, tournament_id, bracket_id=None)
    result = []
    for s in standings[:limit]:
        team = await session.get(Team, s.team_id)
        result.append({
            "rank": s.rank,
            "team_id": s.team_id,
            "team_name": team.name if team else "Unknown",
            "wins": s.wins,
            "losses": s.losses,
            "draws": s.draws,
            "points": s.points,
            "matches_played": s.matches_played,
        })
    return {"standings": result, "total": len(result)}
