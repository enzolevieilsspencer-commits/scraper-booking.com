-- ============================================
-- SCRIPT DE CRÉATION DES TABLES SUPABASE
-- Pour le projet Booking Scraper
-- ============================================

-- Supprimer les tables existantes si nécessaire (ATTENTION: perte de données)
-- DROP TABLE IF EXISTS scraper_logs;
-- DROP TABLE IF EXISTS rate_snapshots;
-- DROP TABLE IF EXISTS hotels;

-- ============================================
-- TABLE: hotels
-- Stocke les informations des hôtels (client + concurrents)
-- ============================================
CREATE TABLE IF NOT EXISTS hotels (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  location TEXT,
  address TEXT,
  url TEXT NOT NULL UNIQUE,
  stars INTEGER CHECK (stars >= 0 AND stars <= 5),
  "photoUrl" TEXT,
  "isClient" BOOLEAN DEFAULT FALSE,
  "isMonitored" BOOLEAN DEFAULT TRUE,
  "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index pour accélérer les requêtes
CREATE INDEX IF NOT EXISTS idx_hotels_monitored ON hotels("isMonitored");
CREATE INDEX IF NOT EXISTS idx_hotels_url ON hotels(url);

-- Commentaires
COMMENT ON TABLE hotels IS 'Hôtels surveillés (1 client + 5 concurrents)';
COMMENT ON COLUMN hotels."isClient" IS 'true = hôtel du client, false = concurrent';
COMMENT ON COLUMN hotels."isMonitored" IS 'true = scraping actif, false = désactivé';

-- ============================================
-- TABLE: rate_snapshots
-- Stocke les prix scrapés pour chaque date
-- ============================================
CREATE TABLE IF NOT EXISTS rate_snapshots (
  id TEXT PRIMARY KEY,
  "hotelId" TEXT NOT NULL REFERENCES hotels(id) ON DELETE CASCADE,
  "dateCheckin" DATE NOT NULL,
  price FLOAT8 CHECK (price IS NULL OR price >= 0),
  currency TEXT DEFAULT 'EUR',
  available BOOLEAN DEFAULT TRUE,
  "scrapedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index pour performances
CREATE INDEX IF NOT EXISTS idx_rate_snapshots_hotel ON rate_snapshots("hotelId");
CREATE INDEX IF NOT EXISTS idx_rate_snapshots_date ON rate_snapshots("dateCheckin");
CREATE INDEX IF NOT EXISTS idx_rate_snapshots_hotel_date ON rate_snapshots("hotelId", "dateCheckin", "scrapedAt");
CREATE INDEX IF NOT EXISTS idx_rate_snapshots_scraped ON rate_snapshots("scrapedAt");

-- Commentaires
COMMENT ON TABLE rate_snapshots IS 'Historique des prix scrapés (30 jours futurs)';
COMMENT ON COLUMN rate_snapshots.price IS 'Prix minimum de la nuit, NULL si indisponible';
COMMENT ON COLUMN rate_snapshots.available IS 'false si hôtel complet pour cette date';

-- ============================================
-- TABLE: scraper_logs
-- Logs des exécutions du scraper
-- ============================================
CREATE TABLE IF NOT EXISTS scraper_logs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('running', 'success', 'error')),
  "hotelId" TEXT REFERENCES hotels(id) ON DELETE SET NULL,
  "snapshotsCreated" INTEGER DEFAULT 0,
  error TEXT,
  "startedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  "completedAt" TIMESTAMP WITH TIME ZONE
);

-- Index
CREATE INDEX IF NOT EXISTS idx_scraper_logs_status ON scraper_logs(status);
CREATE INDEX IF NOT EXISTS idx_scraper_logs_started ON scraper_logs("startedAt" DESC);

-- Commentaires
COMMENT ON TABLE scraper_logs IS 'Logs d''exécution du scraper pour monitoring';
COMMENT ON COLUMN scraper_logs.status IS 'running, success, ou error';

-- ============================================
-- FONCTION: Mise à jour automatique de updatedAt
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW."updatedAt" = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour hotels
DROP TRIGGER IF EXISTS update_hotels_updated_at ON hotels;
CREATE TRIGGER update_hotels_updated_at
    BEFORE UPDATE ON hotels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- DONNÉES DE TEST (optionnel)
-- ============================================

-- Exemple: Insérer un hôtel de test
-- INSERT INTO hotels (
--   id, name, location, address, url, stars, "isClient", "isMonitored"
-- ) VALUES (
--   'test-hotel-1',
--   'Château de Roussan',
--   'Saint-Rémy-de-Provence',
--   '123 Route de Tarascon, 13210 Saint-Rémy-de-Provence',
--   'https://www.booking.com/hotel/fr/chateau-de-roussan.fr.html',
--   4,
--   true,
--   true
-- );

-- ============================================
-- VÉRIFICATION
-- ============================================

-- Compter les tables créées
SELECT 
  schemaname, 
  tablename 
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename IN ('hotels', 'rate_snapshots', 'scraper_logs');

-- Vérifier les colonnes de hotels
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'hotels'
ORDER BY ordinal_position;

-- ============================================
-- REQUÊTES UTILES POUR LE MONITORING
-- ============================================

-- Voir tous les hôtels surveillés
-- SELECT id, name, location, "isClient", "isMonitored"
-- FROM hotels
-- WHERE "isMonitored" = true
-- ORDER BY "isClient" DESC, name;

-- Voir les derniers prix scrapés
-- SELECT 
--   h.name,
--   rs."dateCheckin",
--   rs.price,
--   rs.available,
--   rs."scrapedAt"
-- FROM rate_snapshots rs
-- JOIN hotels h ON h.id = rs."hotelId"
-- ORDER BY rs."scrapedAt" DESC
-- LIMIT 100;

-- Statistiques par hôtel
-- SELECT 
--   h.name,
--   COUNT(rs.id) as total_snapshots,
--   COUNT(rs.id) FILTER (WHERE rs.available = true) as available_dates,
--   AVG(rs.price) FILTER (WHERE rs.available = true) as avg_price,
--   MIN(rs.price) FILTER (WHERE rs.available = true) as min_price,
--   MAX(rs.price) FILTER (WHERE rs.available = true) as max_price
-- FROM hotels h
-- LEFT JOIN rate_snapshots rs ON h.id = rs."hotelId"
-- WHERE h."isMonitored" = true
-- GROUP BY h.id, h.name
-- ORDER BY h.name;

-- Logs des dernières exécutions
-- SELECT 
--   id,
--   status,
--   "snapshotsCreated",
--   error,
--   "startedAt",
--   "completedAt",
--   EXTRACT(EPOCH FROM ("completedAt" - "startedAt")) as duration_seconds
-- FROM scraper_logs
-- ORDER BY "startedAt" DESC
-- LIMIT 20;

-- ============================================
-- FIN DU SCRIPT
-- ============================================

-- Instructions:
-- 1. Aller sur Supabase → SQL Editor
-- 2. Copier-coller ce script
-- 3. Cliquer sur "Run"
-- 4. Vérifier que les 3 tables sont créées
