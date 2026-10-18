"""Build a 1M-row store table in SQLite, the shape of a typical SIP/MIP table."""
import sqlite3, random, sys
db = sqlite3.connect(sys.argv[1])
db.execute("drop table if exists stores")
db.execute("create table stores (store_id int, retailer text, state text, sector text, opened int, closed int, sqft real, revenue real)")
rnd = random.Random(1)
retailers = [f"Retailer {i}" for i in range(400)]
states = [f"S{i:02d}" for i in range(50)]
sectors = ["Apparel", "Beauty", "Grocery", "Home", "Electronics", "Dollar", "Department", "Sporting"]
db.executemany("insert into stores values (?,?,?,?,?,?,?,?)",
    ((i, rnd.choice(retailers), rnd.choice(states), rnd.choice(sectors), rnd.randint(2015, 2026),
      rnd.choice([0, 0, 0, 1]), rnd.uniform(2e3, 1.5e5), rnd.uniform(1e5, 5e7)) for i in range(1_000_000)))
db.execute("create index ix_sector on stores(sector)")
db.commit()
