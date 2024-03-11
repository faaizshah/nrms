from neo4j import GraphDatabase
import time

start_time = time.time()


class Neo4jLoader:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def create_constraints(self):
        with self.driver.session() as session:
            session.execute_write(self._create_constraints)

    @staticmethod
    def _create_constraints(tx):
        constraints_query = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (radio:Radio) REQUIRE radio.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (track:Track) REQUIRE track.isrc IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (artist:Artist) REQUIRE artist.spotifyId IS UNIQUE"
        ]
        for query in constraints_query:
            try:
                tx.run(query)
            except neo4j.exceptions.ClientError as e:
                print(f"Constraint already exists, skipping: {e.message}")
        

    def load_data(self, cypher_query):
        with self.driver.session() as session:
            session.execute_write(self._execute_query, cypher_query)

    @staticmethod
    def _execute_query(tx, cypher_query):
        tx.run(cypher_query)


loader = Neo4jLoader("neo4j://localhost:7687", "neo4j", "your_secret_password")

loader.create_constraints()

cypher_query = """
CALL apoc.periodic.iterate(
  "LOAD CSV WITH HEADERS FROM 'file:///cm-radio-track-02012024_0_0_0.snappy_part_2.csv' AS row RETURN row",
  "
    MERGE (radio:Radio {id: row.RADIO_ID})
      ON CREATE SET radio.name = row.RADIO_NAME, radio.genre = row.RADIO_GENRE,
                    radio.market = COALESCE(row.RADIO_MARKET, 'Unknown'), radio.city = row.RADIO_CITY, radio.countryCode = row.RADIO_CC
    MERGE (track:Track {isrc: row.ISRC})
      ON CREATE SET track.name = row.TRACK_NAME, track.albumName = row.ALBUM_NAME,
                    track.spotifyPlaylistCount = toInteger(row.SPOTIFY_PLAYLIST_COUNT),
                    track.genres = apoc.convert.fromJsonList(row.GENRES)
    MERGE (radio)-[:PLAYS]->(track)
    WITH row, track
    UNWIND apoc.convert.fromJsonList(row.SPOTIFY_ARTIST_IDS) AS spotifyArtistId
    MERGE (artist:Artist {spotifyId: spotifyArtistId})
      ON CREATE SET artist.name = row.ARTIST_NAME, artist.code = row.ARTIST_CODE, artist.cmArtist = row.CM_ARTIST,
                    artist.genre = apoc.convert.fromJsonList(row.ARTIST_GENRE)
    MERGE (track)-[:COMPOSED_BY]->(artist)
    WITH row, track, artist
    WHERE NOT row.ALBUM_NAME IS NULL AND row.ALBUM_NAME <> ''
    MERGE (album:Album {name: row.ALBUM_NAME})
    MERGE (track)-[:PART_OF]->(album)
    WITH row, track, artist
    UNWIND apoc.convert.fromJsonList(row.SPOTIFY_RELATED_ARTISTS_IDS) AS relatedSpotifyId
    MERGE (relatedArtist:Artist {spotifyId: relatedSpotifyId})
    MERGE (artist)-[:RELATED_TO]->(relatedArtist)
    WITH row, track
    UNWIND apoc.convert.fromJsonList(row.GENRES) AS genreName
    MERGE (genre:Genre {name: genreName})
    MERGE (track)-[:HAS_GENRE]->(genre)
  ",
  {batchSize:1000, parallel:false}
)
"""

loader.load_data(cypher_query)

end_time = time.time()
execution_time = end_time - start_time

print(f"The program execution time is: {execution_time}")

loader.close()
