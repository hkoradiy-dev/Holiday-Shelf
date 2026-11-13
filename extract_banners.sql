-- Holiday Shelf: banner performance extraction (B4)
--
-- Run in the BigQuery console (billing project holiday-shelf-110920130).
-- Download as CSV and save as:  data/banner_performance.csv
--
-- One row per banner (promotion_name) with the funnel the Banner Performance page draws:
--   views        = number of view_promotion events (banner shown)
--   clicks       = number of select_promotion events (banner clicked)
--   click_users  = distinct people who clicked
--   buyers          = of those people, how many bought AFTER their first click (strict)
--   buyers_any_time = of those people, how many bought at any point Nov-Jan
--                     (the plan's 169 / 194 / 115 / 48 may use this looser count)
--
-- Expected (from the team plan, Appendix A):
--   Reach New Heights: 127,841 views / 2,988 clicks / 2,752 people / 169 bought (6.1%)
--   Act Responsible:     3,949 views / 2,953 clicks / 2,785 people / 194 bought (7.0%)
--   Complete Your Collection: 1,627 / 1,585 / 1,535 / 115 (7.5%)
--   Google Mural Collection:    995 / 1,029 /   995 /  48 (4.8%)
-- If your numbers differ a little, tell me; if they are far off, the promotion
-- fields may be stored differently and we will adjust.
--
-- "Bought after clicking" is correlation, not proof the banner caused the purchase:
-- people who click banners may have been going to buy anyway.

WITH promo AS (
  SELECT
    user_pseudo_id,
    event_name,
    event_timestamp,
    item.promotion_name AS banner
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`,
    UNNEST(items) AS item
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
    AND event_name IN ('view_promotion', 'select_promotion')
    AND item.promotion_name IS NOT NULL
    AND item.promotion_name != '(not set)'
),

stats AS (
  SELECT
    banner,
    COUNTIF(event_name = 'view_promotion') AS views,
    COUNT(DISTINCT IF(event_name = 'view_promotion', user_pseudo_id, NULL)) AS view_users,
    COUNTIF(event_name = 'select_promotion') AS clicks,
    COUNT(DISTINCT IF(event_name = 'select_promotion', user_pseudo_id, NULL)) AS click_users
  FROM promo
  GROUP BY banner
),

first_click AS (
  SELECT banner, user_pseudo_id, MIN(event_timestamp) AS first_click_ts
  FROM promo
  WHERE event_name = 'select_promotion'
  GROUP BY banner, user_pseudo_id
),

purchases AS (   -- every purchase event, one row per person per timestamp
  SELECT DISTINCT user_pseudo_id, event_timestamp
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
    AND event_name = 'purchase'
),

bought AS (
  SELECT
    c.banner,
    -- bought_any_time: the person bought at some point in Nov-Jan (before or after the click)
    COUNT(DISTINCT p.user_pseudo_id) AS buyers_any_time,
    -- buyers: the person bought AFTER their first click on the banner (the strict version)
    COUNT(DISTINCT IF(p.event_timestamp > c.first_click_ts, p.user_pseudo_id, NULL)) AS buyers
  FROM first_click c
  JOIN purchases p ON p.user_pseudo_id = c.user_pseudo_id
  GROUP BY c.banner
)

SELECT
  s.banner,
  s.views,
  s.view_users,
  s.clicks,
  s.click_users,
  COALESCE(b.buyers, 0) AS buyers,
  COALESCE(b.buyers_any_time, 0) AS buyers_any_time
FROM stats s
LEFT JOIN bought b USING (banner)
ORDER BY s.views DESC