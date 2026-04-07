<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'message' => 'Method not allowed']);
    exit;
}

$raw = file_get_contents('php://input');
$payload = json_decode($raw ?: '', true);
if (!is_array($payload)) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'message' => 'Invalid JSON payload']);
    exit;
}

$eventType = substr(trim((string)($payload['type'] ?? 'page_view')), 0, 40);
$label = substr(trim((string)($payload['label'] ?? '')), 0, 120);
$section = substr(trim((string)($payload['section'] ?? '')), 0, 80);
$path = substr(trim((string)($payload['path'] ?? '/')), 0, 120);
$referrer = substr(trim((string)($payload['referrer'] ?? '')), 0, 200);
$screen = trim((string)($payload['screen'] ?? ''));
$screen = preg_match('/^\d{1,5}x\d{1,5}$/', $screen) ? $screen : '';
$timezoneOffset = (int)($payload['tz_offset'] ?? 0);

$ip = (string)($_SERVER['REMOTE_ADDR'] ?? '');
$ua = substr((string)($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 240);
$salt = (string)(getenv('NILM_DOCS_TRACKING_SALT') ?: 'nilm-docs-default-salt');
$visitorHash = hash('sha256', $salt . '|' . $ip . '|' . $ua);

$dataDir = __DIR__ . DIRECTORY_SEPARATOR . 'data';
if (!is_dir($dataDir)) {
    mkdir($dataDir, 0775, true);
}

$summaryPath = $dataDir . DIRECTORY_SEPARATOR . 'analytics-summary.json';
$eventLogPath = $dataDir . DIRECTORY_SEPARATOR . 'events-' . gmdate('Y-m') . '.jsonl';
$lockPath = $dataDir . DIRECTORY_SEPARATOR . 'analytics.lock';

$entry = [
    'ts' => gmdate('c'),
    'day' => gmdate('Y-m-d'),
    'type' => $eventType ?: 'page_view',
    'label' => $label,
    'section' => $section,
    'path' => $path,
    'referrer' => $referrer,
    'screen' => $screen,
    'tz_offset' => $timezoneOffset,
    'visitor' => $visitorHash,
];

$lockHandle = fopen($lockPath, 'c+');
if ($lockHandle === false) {
    http_response_code(500);
    echo json_encode(['ok' => false, 'message' => 'Could not open tracking lock']);
    exit;
}

flock($lockHandle, LOCK_EX);

$summary = [
    'updated_at' => gmdate('c'),
    'total_events' => 0,
    'total_page_views' => 0,
    'unique_visitors' => [],
    'unique_visitors_count' => 0,
    'views_by_day' => [],
    'events_by_type' => [],
    'sections' => [],
    'cta_labels' => [],
    'scroll_depth' => [],
];

if (is_file($summaryPath)) {
    $existing = json_decode((string)file_get_contents($summaryPath), true);
    if (is_array($existing)) {
        $summary = array_merge($summary, $existing);
    }
}

$summary['updated_at'] = gmdate('c');
$summary['total_events'] = (int)($summary['total_events'] ?? 0) + 1;
$summary['events_by_type'][$entry['type']] = (int)($summary['events_by_type'][$entry['type']] ?? 0) + 1;
$summary['unique_visitors'][$visitorHash] = gmdate('c');
$summary['unique_visitors_count'] = count($summary['unique_visitors']);

if ($entry['type'] === 'page_view') {
    $summary['total_page_views'] = (int)($summary['total_page_views'] ?? 0) + 1;
    $summary['views_by_day'][$entry['day']] = (int)($summary['views_by_day'][$entry['day']] ?? 0) + 1;
}

if ($entry['type'] === 'section_view' && $entry['section'] !== '') {
    $summary['sections'][$entry['section']] = (int)($summary['sections'][$entry['section']] ?? 0) + 1;
}

if ($entry['type'] === 'cta' && $entry['label'] !== '') {
    $summary['cta_labels'][$entry['label']] = (int)($summary['cta_labels'][$entry['label']] ?? 0) + 1;
}

if ($entry['type'] === 'scroll_depth' && $entry['label'] !== '') {
    $summary['scroll_depth'][$entry['label']] = (int)($summary['scroll_depth'][$entry['label']] ?? 0) + 1;
}

file_put_contents($summaryPath, json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
file_put_contents($eventLogPath, json_encode($entry, JSON_UNESCAPED_SLASHES) . PHP_EOL, FILE_APPEND);

flock($lockHandle, LOCK_UN);
fclose($lockHandle);

echo json_encode(['ok' => true]);
