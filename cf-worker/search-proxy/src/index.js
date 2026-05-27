/**
 * Cloudflare Worker — Free Google Search Proxy
 * Runs on Cloudflare's clean IPs, bypasses VPS IP blocking.
 * 
 * Endpoints:
 * POST /search — Google search, returns business results
 * POST /scrape — Fetch a webpage and extract text
 * 
 * Free tier: 100,000 requests/day
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    if (request.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'POST only' }), {
        status: 405,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    try {
      const body = await request.json();

      if (url.pathname === '/search') {
        return handleSearch(body, corsHeaders);
      }

      if (url.pathname === '/scrape') {
        return handleScrape(body, corsHeaders);
      }

      return new Response(JSON.stringify({ error: 'Unknown endpoint' }), {
        status: 404,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: e.message }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }
  },
};

async function handleSearch(body, corsHeaders) {
  const query = body.query;
  if (!query) {
    return new Response(JSON.stringify({ error: 'query required' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  const num = body.num || 10;
  const userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

  // Try multiple search approaches
  const results = await googleSearch(query, num, userAgent);

  return new Response(JSON.stringify({ results, count: results.length }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

async function googleSearch(query, num, userAgent) {
  const results = [];
  
  // Approach 1: Google Lite (textise dot iitty)
  try {
    const url = `https://www.google.com/search?q=${encodeURIComponent(query)}&num=${num}&hl=en`;
    const resp = await fetch(url, {
      headers: {
        'User-Agent': userAgent,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
      },
      cf: {
        // Use Cloudflare's cache to avoid rate limits
        cacheTtl: 300,
        cacheEverything: true,
      },
    });

    if (resp.ok) {
      const html = await resp.text();
      const parsed = parseGoogleResults(html);
      results.push(...parsed);
    }
  } catch (e) {
    // Google failed, try Bing
  }

  // Approach 2: Bing as fallback
  if (results.length === 0) {
    try {
      const url = `https://www.bing.com/search?q=${encodeURIComponent(query)}&count=${num}`;
      const resp = await fetch(url, {
        headers: {
          'User-Agent': userAgent,
          'Accept': 'text/html,application/xhtml+xml',
          'Accept-Language': 'en-US,en;q=0.9',
        },
      });

      if (resp.ok) {
        const html = await resp.text();
        const parsed = parseBingResults(html);
        results.push(...parsed);
      }
    } catch (e) {
      // Both failed
    }
  }

  // Approach 3: DuckDuckGo Lite
  if (results.length === 0) {
    try {
      const url = `https://lite.duckduckgo.com/lite/?q=${encodeURIComponent(query)}`;
      const resp = await fetch(url, {
        headers: {
          'User-Agent': userAgent,
          'Accept': 'text/html',
          'Accept-Language': 'en-US,en;q=0.9',
        },
      });

      if (resp.ok) {
        const html = await resp.text();
        const parsed = parseDDGLiteResults(html);
        results.push(...parsed);
      }
    } catch (e) {
      // All failed
    }
  }

  // Deduplicate by URL
  const seen = new Set();
  return results.filter(r => {
    const key = r.url.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function parseGoogleResults(html) {
  const results = [];
  
  // Google result pattern: <div class="g"> ... <a href="URL"> ... <h3>TITLE</h3>
  const resultBlocks = html.match(/<div class="g">(.*?)<\/div>\s*<\/div>\s*<\/div>/gs) || [];
  
  for (const block of resultBlocks) {
    const linkMatch = block.match(/<a\s+href="(\/url\?q=|)(https?:\/\/[^"&]+)/);
    const titleMatch = block.match(/<h3[^>]*>(.*?)<\/h3>/s);
    
    if (linkMatch && titleMatch) {
      let url = linkMatch[2] || linkMatch[1];
      // Clean URL
      url = url.replace(/^https?:\/\/www\./, 'https://');
      
      // Skip Google's own domains
      if (url.includes('google.com') || url.includes('youtube.com') || 
          url.includes('googleapis.com') || url.includes('schema.org')) continue;
      
      let title = titleMatch[1].replace(/<[^>]+>/g, '').trim();
      title = decodeHtmlEntities(title);
      
      results.push({ url, title, source: 'google' });
    }
  }

  return results;
}

function parseBingResults(html) {
  const results = [];
  
  const items = html.match(/<li class="b_algo">(.*?)<\/li>/gs) || [];
  
  for (const item of items) {
    const linkMatch = item.match(/<a\s+href="(https?:\/\/[^"]+)"/);
    const titleMatch = item.match(/<a[^>]*>(.*?)<\/a>/s);
    
    if (linkMatch && titleMatch) {
      let url = linkMatch[1];
      
      // Skip Bing redirects - extract real URL
      if (url.includes('bing.com/ck/a')) {
        const uMatch = url.match(/u=a1([a-zA-Z0-9_-]+)/);
        if (uMatch) {
          try {
            // Bing uses a simple encoding
            let encoded = uMatch[1].replace(/-/g, '+').replace(/_/g, '/');
            while (encoded.length % 4) encoded += '=';
            url = atob(encoded);
          } catch (e) {
            continue; // Skip if can't decode
          }
        } else {
          continue;
        }
      }
      
      if (url.includes('bing.com') || url.includes('microsoft.com')) continue;
      
      let title = titleMatch[1].replace(/<[^>]+>/g, '').trim();
      title = decodeHtmlEntities(title);
      
      results.push({ url, title, source: 'bing' });
    }
  }

  return results;
}

function parseDDGLiteResults(html) {
  const results = [];
  
  // DDG Lite: <a class="result-link" href="URL">TITLE</a>
  const links = html.match(/class="result-link"[^>]*href="([^"]+)"[^>]*>([^<]+)</g) || [];
  
  for (const match of links) {
    const parts = match.match(/href="([^"]+)"[^>]*>([^<]+)/);
    if (parts) {
      const url = parts[1];
      const title = decodeHtmlEntities(parts[2].trim());
      
      if (!url.includes('duckduckgo.com')) {
        results.push({ url, title, source: 'ddg' });
      }
    }
  }

  return results;
}

async function handleScrape(body, corsHeaders) {
  const targetUrl = body.url;
  if (!targetUrl) {
    return new Response(JSON.stringify({ error: 'url required' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  try {
    const resp = await fetch(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
      },
      cf: {
        cacheTtl: 60,
      },
    });

    const html = await resp.text();
    
    // Extract emails
    const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
    const emails = [...new Set(html.match(emailRegex) || [])]
      .filter(e => !e.match(/example\.com|test\.com|@google\.|@facebook\.|@twitter\.|@linkedin\.|sentry\.io|wixpress\.com|noreply@|no-reject@/i));

    // Extract title
    const titleMatch = html.match(/<title[^>]*>(.*?)<\/title>/is);
    const title = titleMatch ? decodeHtmlEntities(titleMatch[1].replace(/<[^>]+>/g, '').trim()) : '';

    // Extract meta description
    const descMatch = html.match(/<meta[^>]*name=["']description["'][^>]*content=["']([^"']*)/i) ||
                      html.match(/<meta[^>]*content=["']([^"']*)["'][^>]*name=["']description["']/i);
    const description = descMatch ? decodeHtmlEntities(descMatch[1]) : '';

    // Extract phone numbers
    const phoneRegex = /(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}/g;
    const phones = [...new Set(html.match(phoneRegex) || [])];

    return new Response(JSON.stringify({
      url: targetUrl,
      status: resp.status,
      title,
      description,
      emails: emails.slice(0, 10),
      phones: phones.slice(0, 5),
      html_length: html.length,
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message, url: targetUrl }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
}

function decodeHtmlEntities(text) {
  const entities = {
    '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'",
    '&apos;': "'", '&#x27;': "'", '&#x2F;': '/', '&nbsp;': ' ',
  };
  let result = text;
  for (const [entity, char] of Object.entries(entities)) {
    result = result.replace(new RegExp(entity, 'g'), char);
  }
  return result;
}
