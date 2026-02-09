# 🔗 Intégration avec Next.js

Guide pour connecter votre frontend Next.js avec le scraper Python.

## Architecture

```
Next.js (Vercel)
    ↓ API calls
Python API (Railway) ← Pour ajouter des concurrents
    ↓ Write
Supabase (Database) ← Next.js lit directement
    ↑ Write
Python Scheduler (Railway) ← Scraping automatique
```

## 1. Ajouter un concurrent depuis Next.js

### Côté Next.js: API Route

Créer `/pages/api/competitors/add.ts`:

```typescript
// pages/api/competitors/add.ts
import type { NextApiRequest, NextApiResponse } from "next";

const SCRAPER_API_URL = process.env.SCRAPER_API_URL || "http://localhost:8000";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { url, isClient = false } = req.body;

  if (!url) {
    return res.status(400).json({ error: "URL is required" });
  }

  try {
    // Appeler l'API Python
    const response = await fetch(`${SCRAPER_API_URL}/scrape-hotel`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url,
        isClient,
        isMonitored: true,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json(data);
    }

    res.status(200).json(data);
  } catch (error) {
    console.error("Error calling scraper API:", error);
    res.status(500).json({
      error: "Failed to add competitor",
      details: error.message,
    });
  }
}
```

### Côté Next.js: Composant React

```typescript
// components/AddCompetitor.tsx
import { useState } from "react";

export default function AddCompetitor() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    try {
      const response = await fetch("/api/competitors/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });

      const data = await response.json();

      if (response.ok) {
        setMessage(`✅ ${data.message}`);
        setUrl("");
        // Optionnel: rafraîchir la liste des hôtels
        // router.refresh() ou refetch()
      } else {
        setMessage(`❌ ${data.error || "Erreur"}`);
      }
    } catch (error) {
      setMessage("❌ Erreur de connexion");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 border rounded-lg">
      <h2 className="text-xl font-bold mb-4">Ajouter un concurrent</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block mb-2">URL Booking.com</label>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.booking.com/hotel/fr/..."
            className="w-full p-2 border rounded"
            required
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Scraping en cours..." : "Ajouter"}
        </button>

        {message && (
          <p
            className={
              message.startsWith("✅") ? "text-green-600" : "text-red-600"
            }
          >
            {message}
          </p>
        )}
      </form>
    </div>
  );
}
```

## 2. Lire les données depuis Supabase

### Configuration Supabase dans Next.js

```typescript
// lib/supabase.ts
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
```

### Lire les hôtels

```typescript
// lib/hotels.ts
import { supabase } from "./supabase";

export async function getMonitoredHotels() {
  const { data, error } = await supabase
    .from("hotels")
    .select("*")
    .eq("isMonitored", true)
    .order("name");

  if (error) throw error;
  return data;
}

export async function getHotelPrices(hotelId: string, days = 30) {
  const today = new Date().toISOString().split("T")[0];

  const { data, error } = await supabase
    .from("rate_snapshots")
    .select("*")
    .eq("hotelId", hotelId)
    .gte("dateCheckin", today)
    .order("dateCheckin")
    .limit(days);

  if (error) throw error;
  return data;
}
```

### Composant Dashboard

```typescript
// components/PricesDashboard.tsx
import { useEffect, useState } from 'react'
import { getMonitoredHotels, getHotelPrices } from '@/lib/hotels'

export default function PricesDashboard() {
  const [hotels, setHotels] = useState([])
  const [selectedHotel, setSelectedHotel] = useState(null)
  const [prices, setPrices] = useState([])

  useEffect(() => {
    loadHotels()
  }, [])

  async function loadHotels() {
    const data = await getMonitoredHotels()
    setHotels(data)
    if (data.length > 0) {
      loadPrices(data[0].id)
    }
  }

  async function loadPrices(hotelId: string) {
    const data = await getHotelPrices(hotelId)
    setPrices(data)
    setSelectedHotel(hotelId)
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Prix des 30 prochains jours</h2>

      {/* Sélecteur d'hôtel */}
      <select
        value={selectedHotel}
        onChange={(e) => loadPrices(e.target.value)}
        className="p-2 border rounded mb-4"
      >
        {hotels.map(hotel => (
          <key={hotel.id} value={hotel.id}>
            {hotel.name}
          </option>
        ))}
      </select>

      {/* Tableau des prix */}
      <table className="w-full border">
        <thead>
          <tr>
            <th className="p-2 border">Date</th>
            <th className="p-2 border">Prix</th>
            <th className="p-2 border">Disponibilité</th>
          </tr>
        </thead>
        <tbody>
          {prices.map(price => (
            <tr key={price.id}>
              <td className="p-2 border">{price.dateCheckin}</td>
              <td className="p-2 border">
                {price.available ? `${price.price}€` : '-'}
              </td>
              <td className="p-2 border">
                {price.available ? '✅ Dispo' : '❌ Complet'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

## 3. Variables d'environnement Next.js

Créer `.env.local`:

```env
# Supabase (pour lire les données)
NEXT_PUBLIC_SUPABASE_URL=https://drkfyyyeebvjdzdaiyxf.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=votre_anon_key_ici

# API Python (pour ajouter des concurrents)
SCRAPER_API_URL=https://votre-service.up.railway.app
```

⚠️ Sur Vercel, ajouter ces variables dans **Settings** → **Environment Variables**

### Vérifier que SCRAPER_API_URL pointe vers le bon service

- **Où la définir :** projet **Next.js** → `.env.local` (en local) ou **Vercel** → Settings → Environment Variables.
- **Valeur :** l’**URL publique du service Railway** qui exécute l’API (celui qui a le domaine généré dans Railway → Networking).
  - Exemple : `https://service-principal-production.up.railway.app`
  - **Sans** slash final, **sans** `/extract` à la fin. Next fera lui-même `POST {SCRAPER_API_URL}/extract`.
- **Bon service :** celui dont la **Start Command** / **Dockerfile** lance l’API (`python src/api/server.py` ou `./start.sh`), et qui a un **domaine public** dans Railway (Networking → Public Networking).
- **Test rapide :** ouvrir dans le navigateur `{SCRAPER_API_URL}/` ou `{SCRAPER_API_URL}/health`. Tu dois voir un JSON du type `{"status":"running",...}` ou `{"status":"healthy"}`. Si erreur ou page blanche, l’URL ou le service est incorrect.

### Éviter les erreurs 502 et 400

**502 (Bad Gateway)** — Souvent causé par un timeout ou un cold start Railway.

- **Timeout côté Next.js :** l’appel à `POST {SCRAPER_API_URL}/extract` peut prendre 30–90 s (scraping + chargement). Utiliser un timeout d’au moins **60–90 secondes** et ne pas couper trop tôt.
- Exemple avec `fetch` et `AbortSignal.timeout` (Node 18+) :

```typescript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 90000); // 90 s
const response = await fetch(`${SCRAPER_API_URL}/extract`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ url }),
  signal: controller.signal,
});
clearTimeout(timeoutId);
```

- **Cold start :** au premier appel après une période d’inactivité, Railway peut mettre 30–60 s à démarrer. Un seul retry après 502 peut suffire.

**400 (Bad Request)** — Souvent causé par un body invalide lors de la **création du concurrent** (insert Supabase ou validation côté API).

- Ne **jamais** envoyer `null` pour les champs string ou number. L’API `/extract` renvoie déjà des chaînes vides et `0` pour `stars`, mais côté Next.js, lors de l’insert en base (ou de l’envoi à une API), normaliser explicitement :
  - `name`, `location`, `address`, `photoUrl` → utiliser `payload.name ?? ""`, etc.
  - `stars` → utiliser `payload.stars ?? 0`.
- Exemple avant d’insérer dans Supabase :

```typescript
const payload = await fetchExtract(url); // réponse de POST /extract
const row = {
  name: payload.name ?? "",
  location: payload.location ?? "",
  address: payload.address ?? "",
  photoUrl: payload.photoUrl ?? "",
  stars: payload.stars ?? 0,
  url,
  isClient: false,
  isMonitored: true,
};
await supabase.from("hotels").insert(row);
```

## 4. Graphiques de prix (optionnel)

Utiliser Recharts pour visualiser:

```bash
npm install recharts
```

```typescript
// components/PriceChart.tsx
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

export default function PriceChart({ hotels, pricesData }) {
  // Formatter les données pour Recharts
  const chartData = pricesData.map((date) => {
    const dataPoint = { date };
    hotels.forEach((hotel) => {
      const price = pricesData.find(
        (p) => p.hotelId === hotel.id && p.dateCheckin === date
      );
      dataPoint[hotel.name] = price?.price || null;
    });
    return dataPoint;
  });

  return (
    <LineChart width={800} height={400} data={chartData}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey="date" />
      <YAxis />
      <Tooltip />
      <Legend />
      {hotels.map((hotel, i) => (
        <Line
          key={hotel.id}
          type="monotone"
          dataKey={hotel.name}
          stroke={`hsl(${i * 60}, 70%, 50%)`}
        />
      ))}
    </LineChart>
  );
}
```

## 5. Real-time (optionnel)

Écouter les mises à jour en temps réel:

```typescript
// hooks/useRealtimePrices.ts
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";

export function useRealtimePrices(hotelId: string) {
  const [prices, setPrices] = useState([]);

  useEffect(() => {
    // Charger les prix initiaux
    loadPrices();

    // S'abonner aux changements
    const subscription = supabase
      .channel("rate_snapshots")
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "rate_snapshots",
          filter: `hotelId=eq.${hotelId}`,
        },
        (payload) => {
          setPrices((prev) => [...prev, payload.new]);
        }
      )
      .subscribe();

    return () => {
      subscription.unsubscribe();
    };
  }, [hotelId]);

  async function loadPrices() {
    const { data } = await supabase
      .from("rate_snapshots")
      .select("*")
      .eq("hotelId", hotelId);
    setPrices(data || []);
  }

  return prices;
}
```

## Résumé du flux

1. **Ajout concurrent**: Next.js → API Python → Supabase
2. **Lecture données**: Next.js → Supabase (direct)
3. **Scraping auto**: Scheduler Python → Supabase
4. **Temps réel**: Supabase Realtime → Next.js

Cette architecture sépare bien les responsabilités et optimise les performances ! 🚀
