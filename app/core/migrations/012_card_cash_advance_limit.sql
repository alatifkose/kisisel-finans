-- Kredi kartına nakit avans alt-limiti. Toplam kart limiti içindedir;
-- kullanılabilir nakit avans = cash_advance_limit - ödenmemiş nakit avans anaparası.
ALTER TABLE credit_cards ADD COLUMN cash_advance_limit INTEGER NOT NULL DEFAULT 0;
