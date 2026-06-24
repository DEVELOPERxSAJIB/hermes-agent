#!/usr/bin/env python3
"""
Generate Instagram-style post mockups for 15 RE brokerages.
Each HTML file contains 3 post mockups that look like real Instagram posts.
"""
import json
import os

# 15 Selected brokerages
BROKERAGES = [
    {"name": "Bluechip Real Estate", "city": "Dubai", "state": "UAE", "email": "", "phone": "+971****1212", "address": "Downtown Dubai", "slug": "bluechip-real-estate-dubai"},
    {"name": "Amy Koch", "city": "Phoenix", "state": "AZ", "email": "fscottc21@movephoenix.com", "phone": "+1-602-386-7343", "address": "Scottsdale, Phoenix", "slug": "amy-koch-phoenix"},
    {"name": "Central Commercial Real Estate", "city": "Miami", "state": "FL", "email": "", "phone": "", "address": "390 Northwest 26th Street Miami", "slug": "central-commercial-miami"},
    {"name": "Three Towers For Real Estate & Cont. Co.", "city": "Doha", "state": "Qatar", "email": "", "phone": "", "address": "West Bay, Doha", "slug": "three-towers-doha"},
    {"name": "ULR Properties - Dallas", "city": "Dallas", "state": "TX", "email": "", "phone": "+1-214-233-6158", "address": "2320 North Houston Street Dallas", "slug": "ulr-properties-dallas"},
    {"name": "Inner City Development & Realtors", "city": "Houston", "state": "TX", "email": "", "phone": "", "address": "Houston Heights, Houston", "slug": "inner-city-development-houston"},
    {"name": "GWG Enterprises LLC", "city": "Atlanta", "state": "GA", "email": "", "phone": "+1-404-500-6255", "address": "Buckhead, Atlanta", "slug": "gwg-enterprises-atlanta"},
    {"name": "برج النخيل", "city": "Riyadh", "state": "Saudi Arabia", "email": "", "phone": "+966****1212", "address": "Olaya District, Riyadh", "slug": "najm-alnakhil-riyadh"},
    {"name": "DC Capital Group USA", "city": "Orlando", "state": "FL", "email": "", "phone": "+1-407-907-6442", "address": "Lake Nona, Orlando", "slug": "dc-capital-group-orlando"},
    {"name": "Etmam Real Estate", "city": "Kuwait City", "state": "Kuwait", "email": "", "phone": "", "address": "Sharq, Kuwait City", "slug": "etmam-real-estate-kuwait"},
    {"name": "Nancy Braun", "city": "Charlotte", "state": "NC", "email": "", "phone": "+1-704-997-3794", "address": "South End, Charlotte", "slug": "nancy-braun-charlotte"},
    {"name": "Guardian Towers Real Estate", "city": "Abu Dhabi", "state": "UAE", "email": "", "phone": "", "address": "Corniche, Abu Dhabi", "slug": "guardian-towers-abu-dhabi"},
    {"name": "Real Estate Exchange", "city": "Muscat", "state": "Oman", "email": "", "phone": "", "address": "Al Mouj, Muscat", "slug": "real-estate-exchange-muscat"},
    {"name": "Lantower Brandon Crossroads Leasing Office", "city": "Tampa", "state": "FL", "email": "", "phone": "+1-844-606-4291", "address": "Brandon, Tampa", "slug": "lantower-brandon-tampa"},
    {"name": "Israel, Finley & Ramos REALTORS", "city": "Phoenix", "state": "AZ", "email": "israel@ifrhomes.com", "phone": "+1-623-435-8181", "address": "Phoenix, AZ", "slug": "israel-finley-ramos-phoenix"},
]

# City-specific content themes
CITY_CONTENT = {
    "Dubai": {
        "hashtags": ["#DubaiRealEstate", "#LuxuryLiving", "#DubaiProperties", "#UAE", "#InvestInDubai"],
        "post_themes": [
            {"title": "Luxury Waterfront Living", "caption": "Your dream waterfront villa with panoramic views of the Arabian Gulf. 🌊✨\n\n3 bed | 4 bath | 4,500 sqft\nAED 8,500,000\n\nDM for exclusive viewing 📩", "img_query": "luxury villa dubai waterfront"},
            {"title": "Off-Plan Opportunity", "caption": "🚀 Early investment opportunity in Dubai Hills Estate!\n\n• 20% down payment\n• 5-year payment plan\n• Expected completion 2027\n\nLimited units available. Link in bio for details.", "img_query": "dubai hills estate aerial"},
            {"title": "Market Update", "caption": "📊 Dubai Market Pulse — June 2026\n\n• Villa prices up 12% YoY\n• Apartment transactions +8%\n• Top areas: Palm JBR, Downtown, Creek Harbour\n\nWhat's your next move? 🏗️", "img_query": "dubai skyline night"},
        ]
    },
    "Phoenix": {
        "hashtags": ["#PhoenixRealEstate", "#AZLiving", "#DesertLife", "#PhoenixHomes", "#Arizona"],
        "post_themes": [
            {"title": "Desert Oasis Home", "caption": "🏜️ Just Listed in Scottsdale!\n\nStunning 4-bedroom with mountain views, resort-style backyard, and sparkling pool.\n\n$1,250,000 | 3,200 sqft\n\nOpen house this Saturday 11-2pm!", "img_query": "scottsdale desert home pool"},
            {"title": "First-Time Buyer Tip", "caption": "💡 Thinking about buying in Phoenix?\n\nHere's what $400K gets you in 2026:\n✅ 3 bed / 2 bath\n✅ 1,800+ sqft\n✅ Great school districts\n\nSave this post for later! 📌", "img_query": "phoenix suburban home"},
            {"title": "Investment Spotlight", "caption": "📈 Phoenix metro is BOOMING.\n\n• Population growth: 2.1% annually\n• Job market: +4.5% YoY\n• Rental yields: 6-8%\n\nInvest before everyone else catches on. 🔥", "img_query": "phoenix skyline sunset"},
        ]
    },
    "Miami": {
        "hashtags": ["#MiamiRealEstate", "#MiamiLuxury", "#SouthFlorida", "#BrickellLife", "#MiamiBroker"],
        "post_themes": [
            {"title": "Brickell Heights Condo", "caption": "🌴 Miami living at its finest!\n\nPenthouse in Brickell Heights:\n• 3 bed / 3.5 bath\n• 2,400 sqft + terrace\n• Bay & city views\n\n$1,850,000\n\nYour urban oasis awaits. 🏙️", "img_query": "brickell miami condo luxury"},
            {"title": "Selling Guide", "caption": "📋 Thinking of selling in Miami?\n\nTop 3 upgrades that pay off:\n1. Kitchen renovation (85% ROI)\n2. Curb appeal (100%+ ROI)\n3. Staging (5-10% higher sale price)\n\nDM me for a free home valuation! 💰", "img_query": "miami modern kitchen interior"},
            {"title": "Neighborhood Spotlight", "caption": "📍 Neighborhood Spotlight: Coconut Grove\n\n• Tree-lined streets & waterfront parks\n• Median home price: $1.4M\n• Walkable restaurants & shops\n\nPerfect for families who want island vibes without leaving the city. 🌿", "img_query": "coconut grove miami streets"},
        ]
    },
    "Doha": {
        "hashtags": ["#DohaRealEstate", "#QatarProperties", "#DohaLiving", "#WestBay", "#QatarInvestment"],
        "post_themes": [
            {"title": "West Bay Penthouse", "caption": "✨ Exclusive West Bay Residence\n\n4-bedroom penthouse with:\n• 180° Gulf views\n• Private elevator\n• Smart home technology\n\nQAR 12,000,000\n\nPrivate showings only. 🔑", "img_query": "doha west bay skyline luxury"},
            {"title": "Lusail City Development", "caption": "🏗️ Lusail City is transforming!\n\nQatar's smart city of the future:\n• New commercial district\n• Waterfront living\n• World-class amenities\n\nEarly prices still available. DM for brochure. 📲", "img_query": "lusail city qatar development"},
            {"title": "Market Insight", "caption": "📊 Qatar Real Estate — Q2 2026\n\n• Office demand up 15%\n• Retail rents stable\n• Residential: steady growth\n\nThe market is moving. Are you? 💼", "img_query": "doha qatar skyline evening"},
        ]
    },
    "Dallas": {
        "hashtags": ["#DallasRealEstate", "#DFW", "#TexasHomes", "#DallasLuxury", "#LiveInDallas"],
        "post_themes": [
            {"title": "Uptown Dallas Condo", "caption": "🏙️ Just Sold in Uptown!\n\nThis stunning 2-bedroom at:\n• 1,650 sqft\n• Floor-to-ceiling windows\n• Rooftop pool access\n\nSold in 7 days for over asking! 🎉\n\nWant to know your home's value? Link in bio.", "img_query": "dallas uptown condo modern"},
            {"title": "New Construction", "caption": "🔨 Coming Soon in Frisco!\n\nBrand new 5-bedroom estate:\n• 4,800 sqft\n• 3-car garage\n• Top-rated schools nearby\n\nStarting at $1,100,000\n\nGet in early — this won't last! 🏃", "img_query": "frisco texas new construction home"},
            {"title": "Investor Guide", "caption": "💰 DFW Investment Outlook 2026\n\nWhy investors love Dallas:\n• No state income tax\n• Strong job growth (tech, finance)\n• Cap rates: 5-7%\n\nSave this for your next deal! 📊", "img_query": "dallas texas downtown skyline"},
        ]
    },
    "Houston": {
        "hashtags": ["#HoustonRealEstate", "#HTX", "#TexasRealEstate", "#HoustonHomes", "#SpaceCity"],
        "post_themes": [
            {"title": "Heights Bungalow", "caption": "🏡 Charming Heights Bungalow\n\n3 bed | 2 bath | 2,100 sqft\nOriginal hardwood floors + modern updates\nWalk to restaurants & parks\n\n$625,000\n\nOpen house Sunday 2-4pm! 🔑", "img_query": "houston heights bungalow home"},
            {"title": "Rental Market Update", "caption": "📊 Houston Rental Market — June 2026\n\n• Average 1BR rent: $1,450\n• Occupancy rate: 94%\n• Best areas: Montrose, Heights, Midtown\n\nInvestors — this is your market. 💵", "img_query": "houston texas apartment buildings"},
            {"title": "Luxury Estate",                "caption": "👑 Memorial Luxury Estate\n\n6 bed | 7 bath | 8,200 sqft\nPool, tennis court, 1-acre lot\n\n$4,500,000\n\nPrivate appointment only. DM for details. 📩", "img_query": "houston memorial luxury estate pool"},
        ]
    },
    "Atlanta": {
        "hashtags": ["#AtlantaRealEstate", "#ATLHomes", "#GeorgiaRealEstate", "#Buckhead", "#AtlantaBroker"],
        "post_themes": [
            {"title": "Buckhead Estate", "caption": "🏰 Buckhead Showstopper!\n\n5-bedroom estate with:\n• Chef's kitchen\n• Home theater\n• Resort-style pool\n\n$2,850,000 | 6,500 sqft\n\nYour dream home is waiting. ✨", "img_query": "buckhead atlanta mansion estate"},
            {"title": "First-Time Buyer", "caption": "🏠 First-time buyer in Atlanta?\n\nHere's what $350K gets you:\n✅ 3 bed / 2 bath\n✅ 1,600+ sqft\n✅ Close to MARTA & highways\n\nDM me — I'll guide you through every step! 🤝", "img_query": "atlanta georgia suburban home"},
            {"title": "Market Report", "caption": "📈 Atlanta Market Update — June 2026\n\n• Median home price: $425K (+6% YoY)\n• Days on market: 28\n• Hot neighborhoods: Midtown, Decatur, Brookhaven\n\nSellers — it's YOUR market! 🔥", "img_query": "atlanta midtown skyline"},
        ]
    },
    "Riyadh": {
        "hashtags": ["#RiyadhRealEstate", "#SaudiRealEstate", "#RiyadhProperties", "#KSA", "#Vision2030"],
        "post_themes": [
            {"title": "Olaya District Tower", "caption": "🏢 Premium Office Space — Olaya District\n\n• 2,500 sqft\n• Fully fitted\n• Panoramic city views\n\nSAR 1,200/sqft/year\n\nPrime location for your business. 💼", "img_query": "riyadh olaya district towers"},
            {"title": "New Development", "caption": "🚀 Launching Soon: North Riyadh Project\n\nModern living in the heart of the capital:\n• 2 & 3 bedroom apartments\n• Smart home features\n• Community amenities\n\nRegister now for priority access! 📲", "img_query": "riyadh saudi arabia development"},
            {"title": "Vision 2030 Impact", "caption": "🇸🇦 Real Estate & Vision 2030\n\nSaudi Arabia's transformation is creating:\n• New cities & mega-projects\n• Record investment demand\n• Unprecedented opportunities\n\nBe part of the future. 🌟", "img_query": "riyadh saudi arabia skyline"},
        ]
    },
    "Orlando": {
        "hashtags": ["#OrlandoRealEstate", "#OrlandoHomes", "#FloridaLiving", "#LakeNona", "#OrlandoBroker"],
        "post_themes": [
            {"title": "Lake Nona Home", "caption": "🏡 Lake Nona Living at Its Best!\n\n4 bed | 3 bath | 2,800 sqft\nOpen floor plan + lake views\nTop-rated schools nearby\n\n$725,000\n\nSchedule your tour today! 🔑", "img_query": "lake nona orlando home lake view"},
            {"title": "Vacation Rental ROI",        "caption": "💰 Orlando Vacation Rental Investment\n\nWhy Orlando?\n• 74M+ annual visitors\n• Year-round demand\n• Gross yields: 8-12%\n\nYour investment is waiting. DM for analysis! 📊", "img_query": "orlando florida vacation home pool"},
            {"title": "Relocation Guide",            "caption": "🌴 Moving to Orlando?\n\nTop neighborhoods for families:\n1. Winter Park — charming & walkable\n2. Lake Nona — modern & growing\n3. Dr. Phillips — luxury living\n\nSave this for your move! 📌", "img_query": "winter park orlando florida"},
        ]
    },
    "Kuwait City": {
        "hashtags": ["#KuwaitRealEstate", "#KuwaitCity", "#KuwaitProperties", "#GulfRealEstate", "#Sharq"],
        "post_themes": [
            {"title": "Sharq Commercial", "caption": "🏢 Prime Office Space — Sharq District\n\n• 3,000 sqft\n• Sea views\n• Premium finishes\n\nKWD 18/sqft/month\n\nIdeal for established businesses. 💼", "img_query": "kuwait city sharq district buildings"},
            {"title": "Residential Tower",            "caption": "🌊 Gulf View Apartments\n\n2-bedroom luxury apartment:\n• 180° Gulf views\n• Concierge service\n• Infinity pool\n\nKWD 450,000\n\nLimited units available! 🔑", "img_query": "kuwait city gulf view apartments"},
            {"title": "Market Overview",            "caption": "📊 Kuwait Real Estate — Q2 2026\n\n• Residential: stable growth\n• Commercial: rising demand\n• Investment returns: 5-7%\n\nThe market rewards patience. 💎", "img_query": "kuwait city skyline evening"},
        ]
    },
    "Charlotte": {
        "hashtags": ["#CharlotteRealEstate", "#CLT", "#CharlotteHomes", "#NorthCarolina", "#SouthEnd"],
        "post_themes": [
            {"title": "South End Condo", "caption": "🏙️ South End Charmer!\n\n2 bed | 2 bath | 1,450 sqft\nWalk to breweries, restaurants & light rail\nRooftop terrace with city views\n\n$525,000\n\nUrban living done right. ✨", "img_query": "charlotte south end condo modern"},
            {"title": "Charlotte Growth",            "caption": "📈 Charlotte is BOOMING!\n\n• #2 fastest growing US city\n• Major tech & finance employers\n• Median home price: $410K\n\nStill time to get in! 🚀", "img_query": "charlotte nc skyline skyline"},
            {"title": "Luxury Townhome",            "caption": "🏠 Myers Park Luxury Townhome\n\n3 bed | 3.5 bath | 2,600 sqft\nGourmet kitchen, private garage\nTree-lined historic streets\n\n$985,000\n\nYour Uptown address awaits. 🌳", "img_query": "charlotte myers park townhome"},
        ]
    },
    "Abu Dhabi": {
        "hashtags": ["#AbuDhabiRealEstate", "#AbuDhabi", "#UAE", "#Saadiyat", "#CornicheLiving"],
        "post_themes": [
            {"title": "Saadiyat Island Villa", "caption": "🏝️ Saadiyat Island Luxury Villa\n\n5 bed | 6 bath | 6,000 sqft\nPrivate beach access + infinity pool\nNear Louvre Abu Dhabi\n\nAED 15,000,000\n\nExclusive living. Private viewing only. 🔑", "img_query": "saadiyat island villa abu dhabi"},
            {"title": "Corniche Apartment",            "caption": "🌊 Corniche Road Residence\n\n3-bedroom apartment:\n• Full sea views\n• Premium amenities\n• Prime location\n\nAED 4,200,000\n\nLive where others vacation. 🏖️", "img_query": "abu dhabi corniche apartment view"},
            {"title": "Investment Outlook",            "caption": "📊 Abu Dhabi Real Estate 2026\n\n• Rental yields: 6-8%\n• Freehold areas expanding\n• Foreign ownership: 100%\n\nSmart money is here. 💼", "img_query": "abu dhabi skyline luxury towers"},
        ]
    },
    "Muscat": {
        "hashtags": ["#MuscatRealEstate", "#Oman", "#MuscatProperties", "#AlMouj", "#OmanRealEstate"],
        "post_themes": [
            {"title": "Al Mouj Residence", "caption": "🌊 Al Muscat — Waterfront Living\n\n3 bed | 3 bath | 2,400 sqft\nGolf course & marina views\nResort-style community\n\nOMR 185,000\n\nYour slice of paradise. 🏝️", "img_query": "al mouj muscat waterfront home"},
            {"title": "Commercial Opportunity",            "caption": "🏢 Retail Space — Qurum\n\n• 1,800 sqft\n• High foot traffic area\n• Established commercial zone\n\nOMR 12/sqft/month\n\nPerfect for your next venture! 💼", "img_query": "muscat oman commercial district"},
            {"title": "Oman Market Update",            "caption": "📈 Oman Real Estate — Mid 2026\n\n• Tourism driving demand\n• Muscat: steady growth\n• Foreign ownership: expanding\n\nEarly movers win. 🌟", "img_query": "muscat oman skyline"},
        ]
    },
    "Tampa": {
        "hashtags": ["#TampaRealEstate", "#TampaBay", "#FloridaHomes", "#Brandon", "#TampaBroker"],
        "post_themes": [
            {"title": "Brandon Family Home", "caption": "🏡 Just Listed in Brandon!\n\n4 bed | 2.5 bath | 2,600 sqft\nUpdated kitchen, large yard\nTop-rated schools nearby\n\n$485,000\n\nPerfect for growing families! 👨‍👩‍👧‍👦", "img_query": "brandon tampa family home"},
            {"title": "Tampa Bay Growth",            "caption": "📊 Tampa Bay Market Update\n\n• Population: +3% annually\n• Median home: $395K\n• No state income tax!\n\nWhy everyone's moving to Florida. 🌴", "img_query": "tampa bay florida skyline"},
            {"title": "Waterfront Condo",            "caption": "🌊 Waterfront Living — Tampa Bay\n\n2 bed | 2 bath | 1,600 sqft\nBalcony overlooking the bay\nBoat slip available\n\n$675,000\n\nWake up to water views every day. ☀️", "img_query": "tampa bay waterfront condo"},
        ]
    },
}

# Unsplash image URLs for each city
CITY_IMAGES = {
    "luxury villa dubai waterfront": "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=800&h=800&fit=crop",
    "dubai hills estate aerial": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=800&h=800&fit=crop",
    "dubai skyline night": "https://images.unsplash.com/photo-1512632578888-169bbbc64f33?w=800&h=800&fit=crop",
    "scottsdale desert home pool": "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800&h=800&fit=crop",
    "phoenix suburban home": "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=800&h=800&fit=crop",
    "phoenix skyline sunset": "https://images.unsplash.com/photo-1585191983140-931f3c203b14?w=800&h=800&fit=crop",
    "brickell miami condo luxury": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&h=800&fit=crop",
    "miami modern kitchen interior": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&h=800&fit=crop",
    "coconut grove miami streets": "https://images.unsplash.com/photo-1535498730771-e735b998cd64?w=800&h=800&fit=crop",
    "doha west bay skyline luxury": "https://images.unsplash.com/photo-1549213780-9d1cb798b8f8?w=800&h=800&fit=crop",
    "lusail city qatar development": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800&h=800&fit=crop",
    "doha qatar skyline evening": "https://images.unsplash.com/photo-1549213780-9d1cb798b8f8?w=800&h=800&fit=crop",
    "dallas uptown condo modern": "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800&h=800&fit=crop",
    "frisco texas new construction home": "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=800&h=800&fit=crop",
    "dallas texas downtown skyline": "https://images.unsplash.com/photo-1549923746-c502d488b3ea?w=800&h=800&fit=crop",
    "houston heights bungalow home": "https://images.unsplash.com/photo-1518780664697-55e3ad937233?w=800&h=800&fit=crop",
    "houston texas apartment buildings": "https://images.unsplash.com/photo-1460317442991-0ec209397118?w=800&h=800&fit=crop",
    "houston memorial luxury estate pool": "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=800&h=800&fit=crop",
    "buckhead atlanta mansion estate": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&h=800&fit=crop",
    "atlanta georgia suburban home": "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=800&h=800&fit=crop",
    "atlanta midtown skyline": "https://images.unsplash.com/photo-1587213811864-46e59f6873b1?w=800&h=800&fit=crop",
    "riyadh olaya district towers": "https://images.unsplash.com/photo-1578895101408-1a36b834405b?w=800&h=800&fit=crop",
    "riyadh saudi arabia development": "https://images.unsplash.com/photo-1549213780-9d1cb798b8f8?w=800&h=800&fit=crop",
    "riyadh saudi arabia skyline": "https://images.unsplash.com/photo-1586724237569-9c920b0be2b4?w=800&h=800&fit=crop",
    "lake nona orlando home lake view": "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800&h=800&fit=crop",
    "orlando florida vacation home pool": "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=800&h=800&fit=crop",
    "winter park orlando florida": "https://images.unsplash.com/photo-1535498730771-e735b998cd64?w=800&h=800&fit=crop",
    "kuwait city sharq district buildings": "https://images.unsplash.com/photo-1578895101408-1a36b834405b?w=800&h=800&fit=crop",
    "kuwait city gulf view apartments": "https://images.unsplash.com/photo-1549213780-9d1cb798b8f8?w=800&h=800&fit=crop",
    "kuwait city skyline evening": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800&h=800&fit=crop",
    "charlotte south end condo modern": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&h=800&fit=crop",
    "charlotte nc skyline skyline": "https://images.unsplash.com/photo-1587213811864-46e59f6873b1?w=800&h=800&fit=crop",
    "charlotte myers park townhome": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&h=800&fit=crop",
    "saadiyat island villa abu dhabi": "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=800&h=800&fit=crop",
    "abu dhabi corniche apartment view": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=800&h=800&fit=crop",
    "abu dhabi skyline luxury towers": "https://images.unsplash.com/photo-1549213780-9d1cb798b8f8?w=800&h=800&fit=crop",
    "al mouj muscat waterfront home": "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800&h=800&fit=crop",
    "muscat oman commercial district": "https://images.unsplash.com/photo-1578895101408-1a36b834405b?w=800&h=800&fit=crop",
    "muscat oman skyline": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800&h=800&fit=crop",
    "brandon tampa family home": "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=800&h=800&fit=crop",
    "tampa bay florida skyline": "https://images.unsplash.com/photo-1587213811864-46e59f6873b1?w=800&h=800&fit=crop",
    "tampa bay waterfront condo": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&h=800&fit=crop",
}


def generate_post_html(brokerage, post, post_num, city_content):
    """Generate a single Instagram-style post mockup."""
    name = brokerage["name"]
    city = brokerage["city"]
    state = brokerage["state"]
    hashtags = " ".join(city_content["hashtags"][:5])
    img_url = CITY_IMAGES.get(post["img_query"], f"https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800&h=800&fit=crop")
    
    # Different accent colors per city
    city_colors = {
        "Dubai": "#C9A961",
        "Phoenix": "#E87E29",
        "Miami": "#00CED1",
        "Doha": "#8B4513",
        "Dallas": "#003F87",
        "Houston": "#BF0A30",
        "Atlanta": "#008000",
        "Riyadh": "#006C35",
        "Orlando": "#FF6B35",
        "Kuwait City": "#007A5E",
        "Charlotte": "#00788C",
        "Abu Dhabi": "#C9A961",
        "Muscat": "#B8860B",
        "Tampa": "#006B54",
    }
    accent = city_colors.get(city, "#333")
    
    return f"""
    <div class="post-container">
        <!-- Post Header -->
        <div class="post-header">
            <div class="profile-pic">
                <div class="profile-pic-inner">{name[0]}</div>
            </div>
            <div class="profile-info">
                <div class="username">{name.lower().replace(' ', '_').replace('&', '').replace(',', '')}</div>
                <div class="location">{city}, {state}</div>
            </div>
            <div class="more-btn">•••</div>
        </div>
        
        <!-- Post Image -->
        <div class="post-image">
            <img src="{img_url}" alt="{post['title']}" onerror="this.src='https://placehold.co/800x800/{accent.replace('#','')}/ffffff?text={city.replace(' ','+')}+Real+Estate'">
            <div class="image-overlay">
                <div class="post-num-badge">POST {post_num}</div>
            </div>
        </div>
        
        <!-- Engagement Buttons -->
        <div class="engagement">
            <div class="engagement-left">
                <span class="icon heart">♡</span>
                <span class="icon comment">💬</span>
                <span class="icon share">📤</span>
            </div>
            <div class="engagement-right">
                <span class="icon bookmark">🔖</span>
            </div>
        </div>
        
        <!-- Likes -->
        <div class="likes">
            <span class="likes-count">{120 + post_num * 47} likes</span>
        </div>
        
        <!-- Caption -->
        <div class="caption">
            <span class="caption-username">{name.lower().replace(' ', '_').replace('&', '').replace(',', '')}</span>
            <span class="caption-text">{post['caption']}</span>
        </div>
        
        <!-- Hashtags -->
        <div class="hashtags">{hashtags}</div>
        
        <!-- Post type label -->
        <div class="post-type-label">{post['title']}</div>
    </div>"""


def generate_html(brokerage):
    """Generate full HTML page with 3 Instagram post mockups."""
    city = brokerage["city"]
    name = brokerage["name"]
    slug = brokerage["slug"]
    
    city_content = CITY_CONTENT.get(city, CITY_CONTENT["Phoenix"])
    
    posts_html = ""
    for i, post in enumerate(city_content["post_themes"], 1):
        posts_html += generate_post_html(brokerage, post, i, city_content)
    
    name = brokerage["name"]
    city = brokerage["city"]
    state = brokerage["state"]
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram Mockups — {name} ({city})</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: #fafafa;
            color: #262626;
            padding: 40px 20px;
        }}
        
        .page-header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 12px;
            max-width: 900px;
            margin-left: auto;
            margin-right: auto;
            margin-bottom: 40px;
        }}
        
        .page-header h1 {{
            font-size: 28px;
            margin-bottom: 8px;
        }}
        
        .page-header p {{
            opacity: 0.9;
            font-size: 14px;
        }}
        
        .posts-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 30px;
            justify-content: center;
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        .post-container {{
            width: 320px;
            background: white;
            border: 1px solid #dbdbdb;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        
        .post-header {{
            display: flex;
            align-items: center;
            padding: 12px 14px;
            border-bottom: 1px solid #efefef;
        }}
        
        .profile-pic {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 12px;
        }}
        
        .profile-pic-inner {{
            width: 26px;
            height: 26px;
            border-radius: 50%;
            background: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 700;
            color: #333;
        }}
        
        .profile-info {{
            flex: 1;
        }}
        
        .username {{
            font-weight: 600;
            font-size: 14px;
            color: #262626;
        }}
        
        .location {{
            font-size: 12px;
            color: #8e8e8e;
        }}
        
        .more-btn {{
            font-size: 16px;
            cursor: pointer;
            padding: 4px 8px;
        }}
        
        .post-image {{
            width: 100%;
            height: 320px;
            position: relative;
            overflow: hidden;
        }}
        
        .post-image img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        
        .image-overlay {{
            position: absolute;
            top: 10px;
            right: 10px;
        }}
        
        .post-num-badge {{
            background: rgba(0,0,0,0.6);
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }}
        
        .engagement {{
            display: flex;
            justify-content: space-between;
            padding: 12px 14px 8px;
        }}
        
        .engagement-left {{
            display: flex;
            gap: 14px;
        }}
        
        .icon {{
            font-size: 22px;
            cursor: pointer;
            transition: transform 0.1s;
        }}
        
        .icon:hover {{
            transform: scale(1.1);
        }}
        
        .likes {{
            padding: 0 14px;
            font-weight: 600;
            font-size: 14px;
        }}
        
        .caption {{
            padding: 6px 14px;
            font-size: 14px;
            line-height: 1.5;
            white-space: pre-line;
        }}
        
        .caption-username {{
            font-weight: 600;
            margin-right: 6px;
        }}
        
        .caption-text {{
            font-weight: 400;
        }}
        
        .hashtags {{
            padding: 4px 14px 12px;
            font-size: 13px;
            color: #00376b;
            line-height: 1.6;
        }}
        
        .post-type-label {{
            padding: 8px 14px;
            background: #f5f5f5;
            font-size: 11px;
            font-weight: 600;
            color: #8e8e8e;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-top: 1px solid #efefef;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #8e8e8e;
            font-size: 12px;
        }}
        
        @media (max-width: 768px) {{
            .post-container {{
                width: 100%;
                max-width: 360px;
            }}
        }}
    </style>
</head>
<body>
    <div class="page-header">
        <h1>📱 Instagram Mockups — {name}</h1>
        <p>{city}, {state} • 3 Social Media Post Concepts • Generated by NanoSoft Spy System</p>
    </div>
    
    <div class="posts-grid">
        {posts_html}
    </div>
    
    <div class="footer">
        <p>Generated by NanoSoft Spy System • Social Media Content Concepts for {name}</p>
        <p>These mockups demonstrate what active social media presence could look like.</p>
    </div>
</body>
</html>"""
    
    return html


def generate_email_body(brokerage):
    """Generate personalized email body for spy_targets.json."""
    name = brokerage["name"]
    city = brokerage["city"]
    state = brokerage["state"]
    
    # Use the style from personalized_templates.py
    email = f"""Hi there,

I was looking at {name}'s presence in {city} and noticed your social media channels are pretty quiet right now.

For brokerages in the {city} market, that's usually where warm buyers are scrolling before they ever pick up the phone.

I put together 3 Instagram post concepts specifically for {city} — the kind of content that gets saves, shares, and DMs. I even designed mockups so you can see exactly how they'd look on your feed.

Want me to send them over? No charge, just want your read on them.

If they land, we can talk about what ongoing content support would look like for {name}.

SaJib Shikder
NanoSoft Agency | nanosoft.agency"""
    
    return email


def main():
    output_dir = "/home/ubuntu/nanosoft/spy_mockups"
    os.makedirs(output_dir, exist_ok=True)
    
    spy_targets = []
    
    for brokerage in BROKERAGES:
        slug = brokerage["slug"]
        
        # Generate HTML mockup
        html = generate_html(brokerage)
        html_path = os.path.join(output_dir, f"{slug}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        print(f"✅ Created: {slug}.html")
        
        # Add to spy_targets
        spy_targets.append({
            "brokerage": brokerage["name"],
            "email": brokerage["email"],
            "phone": brokerage["phone"],
            "city": brokerage["city"],
            "state": brokerage["state"],
            "address": brokerage["address"],
            "mockup_file": f"spy_mockups/{slug}.html",
            "email_body": generate_email_body(brokerage),
            "status": "mockups_created",
            "social_media_status": "dead/inactive"
        })
    
    # Write spy_targets.json
    targets_path = "/home/ubuntu/nanosoft/spy_targets.json"
    with open(targets_path, "w", encoding="utf-8") as f:
        json.dump(spy_targets, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Created spy_targets.json with {len(spy_targets)} targets")
    print(f"\n📁 All files saved to: {output_dir}/")
    print(f"📋 Summary: {targets_path}")


if __name__ == "__main__":
    main()
