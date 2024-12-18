# boardgame_advisor.py
import aiohttp
import xmltodict
import asyncio
from typing import List, Dict, Optional

class BoardGameAdvisor:
    BGG_API_BASE = "https://boardgamegeek.com/xmlapi2"

    GAME_MECHANICS = {
        "1": "Deck Building",
        "2": "Worker Placement",
        "3": "Dice Rolling",
        "4": "Card Drafting",
        "5": "Area Control",
        "6": "Tile Placement",
        "7": "Resource Management",
        "8": "Cooperative Play",
        "9": "Hand Management",
        "10": "Set Collection",
        "11": "Auction/Bidding",
        "12": "Route Building",
        "13": "Action Points",
        "14": "Variable Player Powers",
        "15": "Modular Board"
    }

    GAME_CATEGORIES = {
        "1": "Strategy",
        "2": "Family",
        "3": "Party",
        "4": "Thematic",
        "5": "Euro",
        "6": "War Game",
        "7": "Abstract",
        "8": "Cooperative",
        "9": "Economic",
        "10": "Adventure",
        "11": "Card Game",
        "12": "Educational",
        "13": "Miniatures",
        "14": "Puzzle",
        "15": "Civilization"
    }

    async def get_recommendations(self, player_count: int, players: List[Dict]) -> str:
        """Get game recommendations based on player preferences."""
        search_terms = []
        for player in players:
            if player.get('categories'):
                search_terms.extend(cat for cat in player['categories'] if cat not in search_terms)
        
        if not search_terms:
            search_terms = ["Strategy", "Family", "Party"]

        # Search BGG for games
        search_results = await self._search_bgg(" ".join(search_terms))
        
        if not search_results or 'items' not in search_results:
            return "I'm sorry, I couldn't find any games at the moment. Please try again."

        # Process items
        items = search_results['items'].get('item', [])
        if isinstance(items, dict):
            items = [items]
        elif not items:
            items = []

        # Score games
        scored_games = []
        seen_names = set()

        for game in items[:30]:
            try:
                game_id = game['@id']
                details = await self._get_game_details(game_id)
                
                if details and 'items' in details and 'item' in details['items']:
                    score, game_info = await self._process_game(game, details, players, player_count)
                    if score > 0 and game_info['name'] not in seen_names:
                        seen_names.add(game_info['name'])
                        scored_games.append({
                            'score': score,
                            'info': game_info
                        })

            except Exception as e:
                print(f"Error processing game {game.get('@id', 'unknown')}: {str(e)}")
                continue

        # Sort and format recommendations
        scored_games.sort(key=lambda x: x['score'], reverse=True)
        return self._format_recommendations(scored_games[:3])

    async def _search_bgg(self, query: str) -> Dict:
        """Search BoardGameGeek API."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.BGG_API_BASE}/search", 
                                     params={'query': query, 
                                            'type': 'boardgame',
                                            'exact': 0}) as response:
                    if response.status == 200:
                        return xmltodict.parse(await response.text())
            except Exception as e:
                print(f"Search error: {str(e)}")
                return None

    async def _get_game_details(self, game_id: str) -> Dict:
        """Get detailed game information."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.BGG_API_BASE}/thing", 
                                     params={'id': game_id, 
                                            'stats': 1}) as response:
                    if response.status == 202:
                        await asyncio.sleep(2)
                        return await self._get_game_details(game_id)
                    elif response.status == 200:
                        return xmltodict.parse(await response.text())
            except Exception as e:
                print(f"Details error: {str(e)}")
                return None

    async def _process_game(self, game: Dict, details: Dict, players: List[Dict], player_count: int) -> tuple[float, Dict]:
        """Process game details and calculate score."""
        game_details = details['items']['item']
        if isinstance(game_details, list):
            game_details = game_details[0]

        # Get basic game info
        game_info = {
            'name': game['name']['@value'] if isinstance(game['name'], dict) else str(game['name']),
            'min_players': int(game_details['minplayers']['@value']),
            'max_players': int(game_details['maxplayers']['@value']),
            'playtime': int(game_details['playingtime']['@value']),
            'weight': float(game_details['statistics']['ratings']['averageweight']['@value']),
            'rating': float(game_details['statistics']['ratings']['average']['@value']),
            'num_ratings': int(game_details['statistics']['ratings']['usersrated']['@value']),
            'description': game_details.get('description', ''),
            'mechanics': [],
            'categories': []
        }

        # Extract mechanics and categories
        if 'link' in game_details:
            links = game_details['link']
            if isinstance(links, dict):
                links = [links]
            
            for link in links:
                if link['@type'] == 'boardgamemechanic':
                    game_info['mechanics'].append(link['@value'])
                elif link['@type'] == 'boardgamecategory':
                    game_info['categories'].append(link['@value'])

        # Calculate score
        score = self._calculate_score(game_info, players, player_count)
        return score, game_info

    def _calculate_score(self, game_info: Dict, players: List[Dict], player_count: int) -> float:
        """Calculate game score based on preferences."""
        score = 10.0  # Base score

        # Player count check
        if player_count < game_info['min_players'] or player_count > game_info['max_players']:
            return 0.0

        # Rating bonus
        score += game_info['rating']
        score += min(5.0, game_info['num_ratings'] / 1000)

        # Process player preferences
        for player in players:
            # Weight preference
            if 'weight_preference' in player:
                weight_diff = abs(game_info['weight'] - float(player['weight_preference']))
                score -= weight_diff

            # Mechanics matches
            if 'mechanics' in player:
                matches = sum(1 for mech in player['mechanics'] if mech in game_info['mechanics'])
                score += matches * 2

            # Category matches
            if 'categories' in player:
                matches = sum(1 for cat in player['categories'] if cat in game_info['categories'])
                score += matches * 1.5

        return max(0.0, score)

    def _format_recommendations(self, games: List[Dict]) -> str:
        """Format recommendations as HTML."""
        if not games:
            return "<p>No games found matching your criteria.</p>"

        html = ""
        for i, game in enumerate(games, 1):
            info = game['info']
            html += f"""
            <div class="bg-white p-4 rounded-lg shadow-md mb-4">
                <h3 class="text-xl font-bold mb-2">{i}. {info['name']}</h3>
                <div class="space-y-2">
                    <p><span class="font-semibold">Players:</span> {info['min_players']}-{info['max_players']}</p>
                    <p><span class="font-semibold">Playing Time:</span> {info['playtime']} minutes</p>
                    <p><span class="font-semibold">BGG Rating:</span> {info['rating']:.1f}/10 ({info['num_ratings']:,} ratings)</p>
                    <p><span class="font-semibold">Complexity:</span> {info['weight']}/5</p>
                    <p><span class="font-semibold">Mechanics:</span> {', '.join(info['mechanics'][:3])}</p>
                    <p><span class="font-semibold">Categories:</span> {', '.join(info['categories'][:3])}</p>
                    <p class="text-sm mt-2">{info['description'][:200]}...</p>
                </div>
            </div>
            """
        return html