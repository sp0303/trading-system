// main.rs
//
// Hedge-Fund Grade News Intelligence Service (Rust + Axum)

use axum::{
    extract::{Query, State},
    response::IntoResponse,
    routing::get,
    Json, Router,
};
use chrono::{DateTime, Duration, Utc};
use dashmap::DashMap;
use feed_rs::parser;
use futures::{stream::FuturesUnordered, StreamExt};
use once_cell::sync::Lazy;
use regex::Regex;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{collections::HashMap, sync::Arc, time::Duration as StdDuration};
use tracing::{info, warn};

//
// ============================================================
// CONFIG
// ============================================================
//

const PORT: &str = "0.0.0.0:7007";
const REQUEST_TIMEOUT_SECS: u64 = 8;
const CACHE_TTL_SECS: i64 = 120;
const MAX_NEWS_LIMIT: usize = 200;

static USER_AGENT: &str =
    "HedgeFundNewsEngine/1.0 (Linux; Rust; Quant Research Service)";

static RSS_FEEDS: Lazy<Vec<&str>> = Lazy::new(|| {
    vec![
        "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.moneycontrol.com/rss/latestnews.xml",
        "https://www.moneycontrol.com/rss/marketreports.xml",
        "https://www.business-standard.com/rss/markets-106.rss",
        "https://www.thehindubusinessline.com/markets/stock-markets/feeder/default.rss",
        "https://www.financialexpress.com/market/stock-market/feed/",
        "https://www.livemint.com/rss/markets",
    ]
});

//
// ============================================================
// GLOBAL CLIENT
// ============================================================
//

static HTTP: Lazy<Client> = Lazy::new(|| {
    Client::builder()
        .user_agent(USER_AGENT)
        .timeout(StdDuration::from_secs(REQUEST_TIMEOUT_SECS))
        .pool_idle_timeout(StdDuration::from_secs(30))
        .tcp_keepalive(StdDuration::from_secs(30))
        .build()
        .unwrap()
});

//
// ============================================================
// SYMBOL ALIASES
// ============================================================
//

static SYMBOL_ALIASES: Lazy<HashMap<&str, Vec<&str>>> = Lazy::new(|| {
    HashMap::from([
        ("ACC", vec!["ACC Ltd", "Associated Cement"]),
        ("ADANIENT", vec!["Adani Enterprises", "Adani"]),
        ("ADANIPORTS", vec!["Adani Ports", "Adani"]),
        ("AMBUJACEM", vec!["Ambuja Cements", "Ambuja"]),
        ("APOLLOHOSP", vec!["Apollo Hospitals"]),
        ("ASIANPAINT", vec!["Asian Paints"]),
        ("AUROPHARMA", vec!["Aurobindo Pharma"]),
        ("AXISBANK", vec!["Axis Bank"]),
        ("BAJAJ-AUTO", vec!["Bajaj Auto"]),
        ("BAJAJFINSV", vec!["Bajaj Finserv"]),
        ("BAJFINANCE", vec!["Bajaj Finance"]),
        ("BANKBARODA", vec!["Bank of Baroda", "BOB"]),
        ("BEL", vec!["Bharat Electronics", "BEL"]),
        ("BHARTIARTL", vec!["Bharti Airtel", "Airtel"]),
        ("BHEL", vec!["Bharat Heavy Electricals", "BHEL"]),
        ("BOSCHLTD", vec!["Bosch"]),
        ("BPCL", vec!["Bharat Petroleum", "BPCL"]),
        ("BRITANNIA", vec!["Britannia Industries", "Britannia"]),
        ("CIPLA", vec!["Cipla"]),
        ("COALINDIA", vec!["Coal India"]),
        ("DIVISLAB", vec!["Divi's Lab", "Divis"]),
        ("DLF", vec!["DLF Ltd"]),
        ("DRREDDY", vec!["Dr Reddy's", "Dr Reddys"]),
        ("EICHERMOT", vec!["Eicher Motors", "Eicher"]),
        ("ETERNAL", vec![]),
        ("GAIL", vec!["GAIL India", "GAIL"]),
        ("GRASIM", vec!["Grasim Industries"]),
        ("HCLTECH", vec!["HCL Tech", "HCL Technologies"]),
        ("HDFCBANK", vec!["HDFC Bank", "HDFC"]),
        ("HDFCLIFE", vec!["HDFC Life"]),
        ("HEROMOTOCO", vec!["Hero MotoCorp", "Hero Moto"]),
        ("HINDALCO", vec!["Hindalco Industries", "Hindalco"]),
        ("HINDPETRO", vec!["Hindustan Petroleum", "HPCL"]),
        ("HINDUNILVR", vec!["Hindustan Unilever", "HUL"]),
        ("ICICIBANK", vec!["ICICI Bank", "ICICI"]),
        ("IDEA", vec!["Vodafone Idea", "Vi"]),
        ("IDFCFIRSTB", vec!["IDFC First Bank"]),
        ("INDIGO", vec!["InterGlobe Aviation", "IndiGo"]),
        ("INDUSINDBK", vec!["IndusInd Bank"]),
        ("INDUSTOWER", vec!["Indus Towers"]),
        ("INFY", vec!["Infosys"]),
        ("IOC", vec!["Indian Oil", "IOCL"]),
        ("ITC", vec!["ITC Ltd", "ITC"]),
        ("JINDALSTEL", vec!["Jindal Steel"]),
        ("JIOFIN", vec!["Jio Financial"]),
        ("JSWSTEEL", vec!["JSW Steel"]),
        ("KOTAKBANK", vec!["Kotak Mahindra", "Kotak"]),
        ("LT", vec!["Larsen & Toubro", "L&T", "L and T"]),
        ("LTIM", vec!["LTIMindtree"]),
        ("LUPIN", vec!["Lupin Ltd"]),
        ("MARUTI", vec!["Maruti Suzuki", "Maruti"]),
        ("MAXHEALTH", vec!["Max Healthcare"]),
        ("MM", vec!["Mahindra & Mahindra", "M&M"]),
        ("NESTLEIND", vec!["Nestle India", "Nestle"]),
        ("NMDC", vec!["NMDC Ltd"]),
        ("NTPC", vec!["NTPC Ltd"]),
        ("ONGC", vec!["ONGC"]),
        ("PNB", vec!["Punjab National Bank", "PNB"]),
        ("POWERGRID", vec!["Power Grid"]),
        ("RELIANCE", vec!["Reliance Industries", "Reliance", "RIL"]),
        ("SAMMAANCAP", vec![]),
        ("SBILIFE", vec!["SBI Life"]),
        ("SBIN", vec!["State Bank of India", "SBI"]),
        ("SHREECEM", vec!["Shree Cement"]),
        ("SHRIRAMFIN", vec!["Shriram Finance"]),
        ("SUNPHARMA", vec!["Sun Pharma"]),
        ("TATACONSUM", vec!["Tata Consumer"]),
        ("TATAPOWER", vec!["Tata Power"]),
        ("TATASTEEL", vec!["Tata Steel"]),
        ("TCS", vec!["Tata Consultancy Services", "TCS"]),
        ("TECHM", vec!["Tech Mahindra"]),
        ("TITAN", vec!["Titan Company", "Titan"]),
        ("TMPV", vec![]),
        ("TRENT", vec!["Trent Ltd"]),
        ("ULTRACEMCO", vec!["UltraTech Cement"]),
        ("UPL", vec!["UPL Ltd"]),
        ("VEDL", vec!["Vedanta"]),
        ("WIPRO", vec!["Wipro Ltd", "Wipro"]),
        ("YESBANK", vec!["Yes Bank"]),
        ("ZEEL", vec!["Zee Entertainment", "ZEEL"]),
    ])
});

//
// ============================================================
// SENTIMENT DICTIONARY
// ============================================================
//

static BULLISH: Lazy<Vec<(&str, f32)>> = Lazy::new(|| {
    vec![
        ("beats estimates", 0.55),
        ("raises guidance", 0.50),
        ("buyback", 0.35),
        ("strong growth", 0.30),
        ("profit rises", 0.28),
        ("wins order", 0.24),
        ("rallies", 0.22),
        ("surges", 0.22),
        ("upgrade", 0.20),
    ]
});

static BEARISH: Lazy<Vec<(&str, f32)>> = Lazy::new(|| {
    vec![
        ("misses estimates", -0.55),
        ("cuts guidance", -0.50),
        ("loss widens", -0.35),
        ("downgrade", -0.28),
        ("profit falls", -0.26),
        ("margin pressure", -0.25),
        ("falls", -0.20),
        ("slumps", -0.20),
        ("probe", -0.18),
    ]
});

//
// ============================================================
// REGEX
// ============================================================
//

static HTML_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"<[^>]*>").unwrap());

//
// ============================================================
// MODELS
// ============================================================
//

#[derive(Clone)]
struct AppState {
    cache: Arc<DashMap<String, CacheEntry>>,
}

#[derive(Clone)]
struct CacheEntry {
    created_at: DateTime<Utc>,
    payload: NewsResponse,
}

#[derive(Serialize, Deserialize, Clone)]
struct NewsItem {
    title: String,
    summary: String,
    link: String,
    source: String,
    published: Option<String>,
    sentiment_score: f32,
    sentiment_label: String,
    relevance_score: f32,
}

#[derive(Serialize, Deserialize, Clone)]
struct NewsResponse {
    status: String,
    count: usize,
    generated_at: String,
    data: Vec<NewsItem>,
}

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    service: String,
    timestamp: String,
}

#[derive(Serialize)]
struct SentimentResponse {
    symbol: String,
    score: f32,
    label: String,
    headline_count: usize,
}

#[derive(Serialize)]
struct ApiResponse<T> {
    status: String,
    data: T,
}

#[derive(Deserialize)]
struct NewsQuery {
    symbol: Option<String>,
    limit: Option<usize>,
    days_limit: Option<i64>,
}

//
// ============================================================
// HELPERS
// ============================================================
//

fn clean_text(input: &str) -> String {
    HTML_RE
        .replace_all(input, " ")
        .to_string()
        .replace("&nbsp;", " ")
        .replace("&#160;", " ")
        .replace('\n', " ")
        .trim()
        .to_lowercase()
}

fn hash_key(s: &str) -> String {
    let mut h = Sha256::new();
    h.update(s.as_bytes());
    hex::encode(h.finalize())
}

fn sentiment(text: &str) -> (f32, String) {
    let t = clean_text(text);

    let mut score = 0.0;

    for (k, v) in BULLISH.iter() {
        if t.contains(k) {
            score += *v;
        }
    }

    for (k, v) in BEARISH.iter() {
        if t.contains(k) {
            score += *v;
        }
    }

    score = score.clamp(-1.0, 1.0);

    let label = if score >= 0.25 {
        "Bullish"
    } else if score >= 0.08 {
        "Slightly Bullish"
    } else if score <= -0.25 {
        "Bearish"
    } else if score <= -0.08 {
        "Slightly Bearish"
    } else {
        "Neutral"
    };

    (score, label.to_string())
}

fn relevance(title: &str, summary: &str, symbol: &str) -> f32 {
    let mut score: f32 = 0.0;
    let content = format!("{} {}", title, summary).to_lowercase();

    if content.contains(&symbol.to_lowercase()) {
        score += 0.7;
    }

    if let Some(aliases) = SYMBOL_ALIASES.get(symbol) {
        for a in aliases {
            if content.contains(&a.to_lowercase()) {
                score += 0.25;
            }
        }
    }

    score.min(1.0)
}

fn within_days(date: &Option<String>, days: i64) -> bool {
    if let Some(d) = date {
        if let Ok(ts) = DateTime::parse_from_rfc3339(d) {
            let age = Utc::now() - ts.with_timezone(&Utc);
            return age <= Duration::days(days);
        }
    }
    true
}

//
// ============================================================
// FETCHER
// ============================================================
//

async fn fetch_feed(url: &str) -> anyhow::Result<Vec<NewsItem>> {
    let start = std::time::Instant::now();

    let resp = HTTP.get(url).send().await?;
    let bytes = resp.bytes().await?;

    let parsed = parser::parse(&bytes[..])?;

    let source = parsed
        .title
        .map(|x| x.content)
        .unwrap_or_else(|| "Unknown".to_string());

    let mut out = vec![];

    for e in parsed.entries {
        let title = e.title.map(|x| x.content).unwrap_or_default();
        let summary = e.summary.map(|x| x.content).unwrap_or_default();
        let link = e.links.first().map(|x| x.href.clone()).unwrap_or_default();
        let published = e.published.map(|x| x.to_rfc3339());

        let (score, label) = sentiment(&format!("{} {}", title, summary));

        out.push(NewsItem {
            title,
            summary,
            link,
            source: source.clone(),
            published,
            sentiment_score: score,
            sentiment_label: label,
            relevance_score: 0.0,
        });
    }

    info!(
        feed = url,
        items = out.len(),
        latency_ms = start.elapsed().as_millis(),
        "feed_loaded"
    );

    Ok(out)
}

//
// ============================================================
// CORE ENGINE
// ============================================================
//

async fn load_news(symbol: Option<String>, days_limit: i64) -> Vec<NewsItem> {
    let mut futures = FuturesUnordered::new();

    for f in RSS_FEEDS.iter() {
        futures.push(fetch_feed(f));
    }

    let mut items = vec![];

    while let Some(res) = futures.next().await {
        match res {
            Ok(v) => items.extend(v),
            Err(e) => warn!("feed error: {}", e),
        }
    }

    // date filter
    items = items
        .into_iter()
        .filter(|x| within_days(&x.published, days_limit))
        .collect();

    // symbol filter
    if let Some(sym) = symbol.clone() {
        items = items
            .into_iter()
            .filter_map(|mut item| {
                let rel = relevance(&item.title, &item.summary, &sym);
                if rel > 0.0 {
                    item.relevance_score = rel;
                    Some(item)
                } else {
                    None
                }
            })
            .collect();
    }

    // dedupe
    let mut seen = std::collections::HashSet::new();

    items.retain(|x| {
        let key = hash_key(&(x.title.clone() + &x.link));
        seen.insert(key)
    });

    // sort
    items.sort_by(|a, b| {
        b.relevance_score
            .partial_cmp(&a.relevance_score)
            .unwrap()
            .then(b.published.cmp(&a.published))
    });

    items
}

//
// ============================================================
// HANDLERS
// ============================================================
//

async fn health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok".to_string(),
        service: "hedgefund-news-engine".to_string(),
        timestamp: Utc::now().to_rfc3339(),
    })
}

async fn news(
    State(state): State<AppState>,
    Query(q): Query<NewsQuery>,
) -> Json<NewsResponse> {
    let symbol = q.symbol.clone();
    let limit = q.limit.unwrap_or(50).min(MAX_NEWS_LIMIT);
    let days_limit = q.days_limit.unwrap_or(14);

    let cache_key = format!(
        "{}:{}:{}",
        symbol.clone().unwrap_or_default(),
        limit,
        days_limit
    );

    if let Some(entry) = state.cache.get(&cache_key) {
        let age = Utc::now() - entry.created_at;
        if age.num_seconds() <= CACHE_TTL_SECS {
            return Json(entry.payload.clone());
        }
    }

    let mut data = load_news(symbol, days_limit).await;
    data.truncate(limit);

    let payload = NewsResponse {
        status: "success".to_string(),
        count: data.len(),
        generated_at: Utc::now().to_rfc3339(),
        data,
    };

    state.cache.insert(
        cache_key,
        CacheEntry {
            created_at: Utc::now(),
            payload: payload.clone(),
        },
    );

    Json(payload)
}

async fn sentiment_handler(
    Query(q): Query<NewsQuery>,
) -> impl IntoResponse {
    let symbol = q.symbol.unwrap_or_else(|| "MARKET".to_string());

    let data = load_news(Some(symbol.clone()), 14).await;

    let count = data.len();

    let avg = if count == 0 {
        0.0
    } else {
        data.iter()
            .map(|x| x.sentiment_score)
            .sum::<f32>()
            / count as f32
    };

    let label = if avg > 0.15 {
        "Bullish"
    } else if avg > 0.05 {
        "Slightly Bullish"
    } else if avg < -0.15 {
        "Bearish"
    } else if avg < -0.05 {
        "Slightly Bearish"
    } else {
        "Neutral"
    };

    Json(ApiResponse {
        status: "success".to_string(),
        data: SentimentResponse {
            symbol,
            score: (avg * 1000.0).round() / 1000.0,
            label: label.to_string(),
            headline_count: count,
        },
    })
}

//
// ============================================================
// MAIN
// ============================================================
//

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let state = AppState {
        cache: Arc::new(DashMap::new()),
    };

    let app = Router::new()
        .route("/health", get(health))
        .route("/news", get(news))
        .route("/sentiment", get(sentiment_handler))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(PORT).await.unwrap();

    info!("🚀 Hedge Fund News Engine running on {}", PORT);

    axum::serve(listener, app).await.unwrap();
}
