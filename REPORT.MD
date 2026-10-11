# Holiday Shelf 🎄

**A data-driven holiday merchandising decision tool**

Holiday Shelf helps store merchandisers identify which products deserve homepage placements, category-page visibility, and promotional banner space during the holiday season.

Instead of relying on views or sales alone, the application analyzes product exposure, purchases, and conversion performance to uncover proven winners, overlooked opportunities, and products that may not deserve additional visibility.

## 🎯 Project Overview

Merchandisers often face a challenge: products that receive the most attention are not always the products that convert best.

For example:
- Some products receive many views but generate very few purchases.
- Some products receive little visibility but sell well whenever shoppers encounter them.
- Some products perform consistently well and deserve continued promotion.

Holiday Shelf addresses this problem by analyzing product-level shopping behavior and grouping products into actionable categories. The ultimate goal is to help merchandisers build a smarter shortlist of 10–15 products for holiday promotions.

## 📊 Data Source

This project uses Google's public sample e-commerce dataset in BigQuery:

`bigquery-public-data.ga4_obfuscated_sample_ecommerce`

The dataset contains anonymized shopping activity from the Google Merchandise Store between **November 1, 2020, and January 31, 2021**, covering a complete holiday season.

A custom SQL query was executed in BigQuery to aggregate the following product-level metrics:

- **Views:** Shopping sessions in which a product detail page was viewed.
- **Add-to-cart sessions:** Shopping sessions in which a product was added to the cart.
- **Purchases:** Shopping sessions associated with a product purchase.
- **Promotion exposure:** Shopping sessions in which a product appeared in a promotional event.

The query results were exported to CSV for local processing.

**Raw dataset:** `data/raw_events.csv`

- Approximately 126,000 rows
- One row per product per day
- Used as the starting point for the data-processing pipeline

## 🔍 Data Quality and Methodology

Before developing the visualizations, we investigated the raw data to identify inconsistencies and limitations that could distort merchandising decisions.

### 1. Product Category Inconsistencies

The same product ID appeared under multiple category labels, including blank categories and different category paths.

For example, a single Android sticker appeared under labels such as `New`, blank, `Home/Stationery/Stickers/`, and `Home/Shop by Brand/Android/`.

Treating these records as separate products would fragment the product's activity and produce misleading results.

**Solution:** The pipeline assigns each product ID its most frequently occurring category label, providing a consistent product identity throughout the analysis.

### 2. Product Views Underestimate Actual Exposure

An initial investigation revealed that approximately **96% of recorded purchases were associated with products having zero recorded product-detail-page views**.

We verified this behavior using a simpler query directly in BigQuery. The finding was not caused by an error in our processing code; it reflects a limitation in how the dataset records product views.

Shoppers may interact with products through listing pages, quick-add buttons, recommendations, or other shopping paths without opening the full product detail page.

Consequently, product views alone are not a reliable measure of visibility.

**Solution: Sessions Exposed**

We use the following proxy for product exposure:

`Sessions Exposed = View Sessions + Add-to-Cart Sessions`

This provides a more useful exposure measure than product views alone. However, it is a proxy rather than a fully deduplicated count of unique exposed sessions. A session that both views and adds a product to the cart may be counted in both metrics.

### 3. Purchases Can Exceed Recorded Exposure

Even after introducing the exposure proxy, approximately half of the products have purchase counts that exceed their recorded exposure counts.

This suggests that some purchase activity may occur through paths not fully captured by the available exposure metrics.

Rather than silently treating these counts as reliable conversion observations, the application flags affected products so that merchandisers can interpret their results cautiously.

## 🧮 Product Performance Metrics

Holiday Shelf calculates product-level metrics to help compare visibility and purchasing behavior.

| Metric | Purpose |
|---|---|
| Views | Measures recorded product detail page interest |
| Add-to-cart sessions | Measures recorded cart engagement |
| Purchases | Measures recorded purchasing activity |
| Sessions exposed | Estimates product exposure using views and add-to-cart sessions |
| Conversion rate | Compares purchases with the exposure proxy |
| Wilson confidence interval | Communicates uncertainty around an estimated conversion rate |
| Data-quality flag | Identifies products whose purchase counts exceed recorded exposure |

Conversion rates and confidence intervals should be interpreted in light of the dataset's tracking limitations. In particular, purchase counts that exceed recorded exposure can produce inflated or otherwise misleading conversion estimates.

### Wilson Confidence Intervals

A conversion rate alone does not show how much evidence supports the estimate.

For example, a product with a 20% conversion rate based on 100 observations is generally less precisely estimated than a product with the same rate based on 5,000 observations.

Holiday Shelf uses Wilson confidence intervals to communicate this uncertainty, helping merchandisers distinguish promising products supported by substantial evidence from products with limited observations.

## 🏷️ Product Performance Categories

Products are grouped according to their relative exposure and conversion performance.

| Category | Meaning | Merchandising Implication |
|---|---|---|
| ⭐ Star | High exposure and strong conversion | Maintain visibility for proven winners |
| 💎 Hidden Gem | Low exposure and strong conversion | Consider increasing visibility |
| 🪟 Window-Shopper | High exposure and weak conversion | Review whether the product deserves additional promotional space |
| 📉 Low Priority | Low exposure and weak conversion | Consider deprioritizing the product |
| ⚠️ Not Enough Data | Insufficient observations for a reliable classification | Gather more evidence before making a decision |

### Relative Performance Thresholds

The classification system compares products with one another rather than using fixed business thresholds.

The median exposure and median conversion rate among products with sufficient data serve as the reference points for determining high and low performance.

A product must perform **strictly better than the median** to qualify as high-performing on a given metric. This distinction is important when the median conversion rate is zero.

### A Classification Bug We Identified and Fixed

An early version of the classification logic assigned nearly every product to either Star or Hidden Gem, leaving the Window-Shopper category empty.

The underlying problem was a zero median conversion rate. The original comparison treated a conversion rate equal to zero as meeting the high-performance threshold.

Because conversion rates cannot be negative, nearly every product passed that condition.

We corrected the comparison to require a conversion rate strictly greater than the median. This produced a more meaningful distribution across the performance categories.

This finding reinforced an important principle of the project: successful code execution does not guarantee analytically correct results. The underlying metrics and classification outputs must also be validated.

## 🛠️ Technology Stack

The current project uses:

- **Python** — Data processing and analytics
- **Pandas** — Data cleaning, aggregation, and metric calculation
- **SQL / Google BigQuery** — Source data extraction and validation
- **CSV** — Input data format
- **Data visualization** — Interactive product performance scorecard

Additional technologies and visualization libraries can be documented here as the application evolves.

## 📁 Project Structure

```text
Holiday-Shelf/
├── data/
│   └── raw_events.csv
├── app.py
├── pipeline.py
├── requirements.txt
└── README.md
```

- `app.py` — Application entry point and Shelf Scorecard interface.
- `pipeline.py` — Data cleaning, metric calculations, confidence intervals, and product classification.
- `data/raw_events.csv` — Raw product-level event data exported from BigQuery.
- `requirements.txt` — Python dependencies.
- `README.md` — Project overview, methodology, and documentation.

## 🚧 Current Development Status

### Completed

- [x] Extracted product event data from Google BigQuery.
- [x] Exported the raw query results to CSV.
- [x] Investigated inconsistent product category labels.
- [x] Implemented category normalization by product ID.
- [x] Identified the limitations of product-detail-page views.
- [x] Introduced the sessions-exposed proxy.
- [x] Added product performance metrics and data-quality flags.
- [x] Implemented Wilson confidence intervals.
- [x] Developed the product classification logic.
- [x] Fixed the zero-median conversion classification bug.
- [x] Built the Shelf Scorecard page.

### In Progress / Planned

- [ ] **Promo Check:** Build visualizations for evaluating promotional exposure and product outcomes.
- [ ] **Season Playbook:** Develop seasonal insights and recommendations from product performance patterns.
- [ ] **Shortlist Builder:** Create a workflow that helps merchandisers select and prioritize 10–15 products for holiday promotion.
- [ ] **AI Rationale Layer:** Generate clear, evidence-based explanations for why products are recommended, including relevant metrics, uncertainty, and data-quality warnings.

## 🚀 Getting Started

### Prerequisites

- Python 3 installed
- Git installed
- A local copy of this repository

### 1. Clone the repository

```bash
git clone https://github.com/hkoradiy-dev/Holiday-Shelf.git
cd Holiday-Shelf
```

### 2. Create a virtual environment

On macOS or Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the application

```bash
python app.py
```

Follow any instructions printed by the application to access the interface.

**Note:** The run command may need to change if `app.py` uses a framework-specific development server. Update this section once the application's framework and launch configuration are confirmed.

## 👥 Team Collaboration

Holiday Shelf is being developed collaboratively using GitHub.

To contribute:

1. Clone the repository.
2. Create a feature branch.
3. Implement and test your changes.
4. Commit your changes with a descriptive message.
5. Push the branch to GitHub.
6. Open a Pull Request for review before merging into `main`.

Example:

```bash
git checkout -b feature/shortlist-builder
git add .
git commit -m "Add shortlist builder"
git push -u origin feature/shortlist-builder
```

Keep commits focused, avoid committing secrets or unnecessary generated files, and document significant changes.

## ⚠️ Limitations

- The dataset is anonymized sample data from a historical holiday season, not live store activity.
- Product-detail-page views do not capture every way shoppers encounter products.
- The sessions-exposed metric is a proxy and may count the same session more than once.
- Purchases can exceed recorded exposure counts for some products, making their conversion estimates unreliable.
- Median-based categories describe relative performance within this dataset and do not guarantee future results.
- Confidence intervals communicate sampling uncertainty but do not correct tracking bias or missing exposure information.
- Product recommendations should support, not replace, merchandising judgment.

## 🎯 Project Goal

The ultimate goal of Holiday Shelf is to turn raw e-commerce event data into an actionable holiday merchandising shortlist.

By combining product exposure, conversion performance, statistical uncertainty, data-quality checks, and explainable recommendations, the application aims to help merchandisers identify overlooked opportunities and make more informed promotional decisions.

---

**Holiday Shelf — Find the products worth putting on the shelf.**