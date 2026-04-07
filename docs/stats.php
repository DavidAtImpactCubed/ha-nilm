<?php
declare(strict_types=1);

$summaryPath = __DIR__ . DIRECTORY_SEPARATOR . 'data' . DIRECTORY_SEPARATOR . 'analytics-summary.json';
$summary = [];
if (is_file($summaryPath)) {
    $loaded = json_decode((string)file_get_contents($summaryPath), true);
    if (is_array($loaded)) {
        $summary = $loaded;
    }
}

$requireKey = (string)(getenv('NILM_DOCS_STATS_KEY') ?: '');
$givenKey = (string)($_GET['key'] ?? '');
$authorized = ($requireKey === '') || hash_equals($requireKey, $givenKey);

function top_items(array $items, int $limit = 10): array
{
    arsort($items);
    return array_slice($items, 0, $limit, true);
}

$viewsByDay = top_items(array_reverse((array)($summary['views_by_day'] ?? []), true), 14);
$topSections = top_items((array)($summary['sections'] ?? []), 10);
$topCtas = top_items((array)($summary['cta_labels'] ?? []), 10);
$topTypes = top_items((array)($summary['events_by_type'] ?? []), 10);
$scrollDepth = top_items((array)($summary['scroll_depth'] ?? []), 10);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NILM Docs Usage Stats</title>
    <link rel="stylesheet" href="./assets/docs.css">
</head>
<body>
    <main class="content stats-page">
        <section class="hero">
            <span class="hero-kicker">Analytics</span>
            <h2>Documentation Usage Stats</h2>
            <p>This page summarizes the usage tracked by the built-in PHP analytics endpoint.</p>
        </section>

        <?php if (!$authorized): ?>
            <section class="doc-section">
                <div class="section-head">
                    <span class="eyebrow">Protected</span>
                    <h2>Access key required</h2>
                    <p>This stats page is protected. Add the correct <code>?key=...</code> value to the URL.</p>
                </div>
            </section>
        <?php else: ?>
            <section class="doc-section">
                <div class="card-grid stats-grid">
                    <article class="info-card">
                        <h4>Total page views</h4>
                        <p class="metric"><?= htmlspecialchars((string)((int)($summary['total_page_views'] ?? 0))) ?></p>
                    </article>
                    <article class="info-card">
                        <h4>Total events</h4>
                        <p class="metric"><?= htmlspecialchars((string)((int)($summary['total_events'] ?? 0))) ?></p>
                    </article>
                    <article class="info-card">
                        <h4>Unique visitors</h4>
                        <p class="metric"><?= htmlspecialchars((string)((int)($summary['unique_visitors_count'] ?? 0))) ?></p>
                    </article>
                </div>
            </section>

            <section class="doc-section">
                <div class="section-head">
                    <span class="eyebrow">Summary</span>
                    <h2>Recent usage</h2>
                    <p>Use these sections to understand which parts of the docs are most interesting to users.</p>
                </div>

                <div class="stats-columns">
                    <div class="info-card">
                        <h4>Views by day</h4>
                        <ul class="bullet-list compact">
                            <?php foreach ($viewsByDay as $day => $count): ?>
                                <li><?= htmlspecialchars((string)$day) ?>: <?= htmlspecialchars((string)$count) ?></li>
                            <?php endforeach; ?>
                        </ul>
                    </div>

                    <div class="info-card">
                        <h4>Most viewed sections</h4>
                        <ul class="bullet-list compact">
                            <?php foreach ($topSections as $name => $count): ?>
                                <li><?= htmlspecialchars((string)$name) ?>: <?= htmlspecialchars((string)$count) ?></li>
                            <?php endforeach; ?>
                        </ul>
                    </div>

                    <div class="info-card">
                        <h4>Top CTA clicks</h4>
                        <ul class="bullet-list compact">
                            <?php foreach ($topCtas as $name => $count): ?>
                                <li><?= htmlspecialchars((string)$name) ?>: <?= htmlspecialchars((string)$count) ?></li>
                            <?php endforeach; ?>
                        </ul>
                    </div>

                    <div class="info-card">
                        <h4>Event types</h4>
                        <ul class="bullet-list compact">
                            <?php foreach ($topTypes as $name => $count): ?>
                                <li><?= htmlspecialchars((string)$name) ?>: <?= htmlspecialchars((string)$count) ?></li>
                            <?php endforeach; ?>
                        </ul>
                    </div>

                    <div class="info-card">
                        <h4>Scroll depth</h4>
                        <ul class="bullet-list compact">
                            <?php foreach ($scrollDepth as $label => $count): ?>
                                <li><?= htmlspecialchars((string)$label) ?>: <?= htmlspecialchars((string)$count) ?></li>
                            <?php endforeach; ?>
                        </ul>
                    </div>

                    <div class="info-card">
                        <h4>Last update</h4>
                        <p><?= htmlspecialchars((string)($summary['updated_at'] ?? 'No data yet')) ?></p>
                        <p class="muted-note">Set the environment variable <code>NILM_DOCS_STATS_KEY</code> on the host to protect this page with <code>?key=...</code>.</p>
                    </div>
                </div>
            </section>
        <?php endif; ?>
    </main>
</body>
</html>
