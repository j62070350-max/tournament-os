async def _post_registration_panel(tournament_id: str, organization_id: str) -> None:
    """
    Automatically posts the registration panel into the designated channel.
    This is triggered by the autonomous engine when a tournament moves to REGISTRATION_OPEN.
    """
    from app.database.session import AsyncSessionLocal
    from app.database.models.tournament import Tournament
    from app.database.models.guild import Guild
    from app.bot.views.player_hub_view import PlayerHubView
    from app.services.notification.discord_delivery import get_bot
    from sqlalchemy import select

    bot = get_bot()
    if not bot:
        logger.error("Cannot post reg panel: Bot not registered")
        return

    async with AsyncSessionLocal() as session:
        tournament = await session.get(Tournament, tournament_id)
        if not tournament:
            return

        guild_q = select(Guild).where(Guild.organization_id == organization_id).limit(1)
        guild = (await session.execute(guild_q)).scalar_one_or_none()
        if not guild:
            return

        # Find the registration channel
        # Priority: tournament.registration_channel_id -> guild.channel_ids['registration']
        reg_channel_id = tournament.channel_config.get("registration_channel_id") if tournament.channel_config else None
        if not reg_channel_id:
            guild_settings = guild.settings or {}
            reg_channel_id = guild_settings.get("channel_ids", {}).get("registration")

        if not reg_channel_id:
            logger.error("No registration channel configured for tournament %s", tournament_id[:8])
            return

        channel = bot.get_channel(int(reg_channel_id))
        if not channel:
            logger.error("Registration channel %s not found in Discord", reg_channel_id)
            return

        # Create the persistent registration view
        view = PlayerHubView(tournament_id=tournament_id, organization_id=organization_id)
        
        # Post the registration embed
        from app.bot.helpers.formatters import tournament_embed
        embed = tournament_embed(tournament)
        embed.description = f"📝 **Registration is now OPEN!**\n\nClick the button below to join the tournament."
        
        await channel.send(embed=embed, view=view)
        logger.info("Auto-posted registration panel for tournament %s in channel %s", tournament_id[:8], reg_channel_id)


async def _auto_generate_first_round(tournament_id: str, organization_id: str) -> None:
    """
    Initializes the tournament bracket and creates the first round of match channels.
    """
    from app.database.session import AsyncSessionLocal
    from app.database.models.tournament import Tournament
    from app.database.repositories.bracket import BracketRepository
    from app.services.bracket.generator import BracketGenerator
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        async with session.begin():
            t = await session.get(Tournament, tournament_id)
            if not t:
                return
            
            # Generate the bracket
            gen = BracketGenerator(session)
            bracket = await gen.generate(
                organization_id=organization_id,
                tournament_id=tournament_id,
                format=t.format,
                stage=1
            )
            
            # Get the matches generated for the first round
            # The generator likely creates Match objects in the DB already.
            # We just need to find them to trigger channel creation.
            from app.database.models.match import Match
            match_q = select(Match).where(
                Match.tournament_id == tournament_id,
                Match.round == 1
            )
            result = await session.execute(match_q)
            first_round_matches = result.scalars().all()
            match_ids = [m.id for m in first_round_matches]

        # Create channels and notify players
        if match_ids:
            await _create_match_channels(organization_id, tournament_id, match_ids)
            logger.info("Auto-generated first round for tournament %s (%d matches)", tournament_id[:8], len(match_ids))
