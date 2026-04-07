<?php
$githubRepoUrl = 'https://github.com/lgarciamarrero92/ha-nilm';
$haAddRepositoryUrl = 'https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Flgarciamarrero92%2Fha-nilm';

$journeys = [
    [
        'title' => 'First-time setup',
        'body' => 'Start here if you have just installed the apps and want to reach a working NILM setup inside Home Assistant.',
        'href' => '#installation',
    ],
    [
        'title' => 'Preview and validate models',
        'body' => 'Use this path if your goal is to understand Energy Dashboard, historical disaggregation, and model debugging.',
        'href' => '#energy-dashboard',
    ],
    [
        'title' => 'Train an appliance model',
        'body' => 'Use this path if you want to prepare appliance data, send a training job, and validate the trained model afterward.',
        'href' => '#training',
    ],
];

$valueProps = [
    [
        'title' => 'Turn one mains sensor into appliance insight',
        'body' => 'NILM uses a single aggregate power signal and learned appliance models to estimate what individual appliances are doing, without requiring one physical smart plug for every device.',
    ],
    [
        'title' => 'Train models from your own Home Assistant history',
        'body' => 'Instead of relying only on generic signatures, you can create appliance models from your own data, which makes the system better adapted to your home, your devices, and your sensors.',
    ],
    [
        'title' => 'Move from raw power to actionable entities',
        'body' => 'Once a model is good enough, NILM can publish live appliance power and on/off entities back into Home Assistant so you can use them in dashboards, automations, and energy workflows.',
    ],
];

$useCases = [
    'Understand which appliances are likely responsible for peaks in mains power.',
    'Create virtual appliance entities for devices that do not have dedicated sensors.',
    'Compare trained models on historical intervals before enabling live publishing.',
    'Debug appliance behavior by inspecting predicted power, ON/OFF state, probability p, and threshold thr.',
    'Build a more detailed energy view in Home Assistant without full hardware submetering.',
];

$whatNilmMeans = [
    'NILM stands for Non-Intrusive Load Monitoring.',
    'Non-intrusive means the system works from an aggregate mains signal instead of requiring a dedicated physical meter on each appliance.',
    'Load monitoring means the system tries to infer appliance-level behavior such as estimated power and ON/OFF state from that aggregate signal.',
    'In practical Home Assistant terms, NILM tries to answer a question like: "Given only my mains power, what is my fridge, oven, or dishwasher likely doing right now?"',
];

$howItWorks = [
    'NILM starts from one mains power sensor that represents the total consumption of the home or monitored circuit.',
    'The user prepares appliance training data from Home Assistant history, either with manual intervals or with a ground-truth appliance sensor.',
    'The training server turns that prepared data into an appliance model that represents the target appliance in the embedding space used by the system.',
    'Later, the NILM app compares the live or historical mains signal against those trained appliance models and estimates appliance-level power and ON/OFF behavior.',
    'The result can be previewed in the dashboard and, if useful, published as live Home Assistant entities.',
];

$expectations = [
    'NILM is an estimation system, not a certified submeter. It is useful for insight, monitoring, debugging, and automations, but it will not always be perfect.',
    'The better the mains signal quality and the better the training examples, the better the appliance-level predictions tend to be.',
    'Some appliances are easier than others. Distinctive, repeatable signatures are usually easier to learn and validate than subtle or overlapping ones.',
    'The product is most useful when you want a practical middle ground between "only mains power" and "a hardware meter on every device."',
];

$ilmVsNilm = [
    [
        'title' => 'ILM: Intrusive Load Monitoring',
        'body' => 'ILM usually means measuring appliances with dedicated hardware such as smart plugs, clamp meters, or individual submeters. It gives direct readings per device, but it requires more hardware, more installation effort, and usually a higher cost as the number of monitored appliances grows.',
    ],
    [
        'title' => 'NILM: Non-Intrusive Load Monitoring',
        'body' => 'NILM starts from a single aggregate mains signal and tries to infer appliance-level behavior with trained models. It is less direct than ILM, but far easier and cheaper to scale because you do not need one physical meter per appliance.',
    ],
    [
        'title' => 'Why the tradeoff is attractive',
        'body' => 'For many Home Assistant users, the goal is not laboratory-grade submetering. The goal is useful visibility, virtual appliance entities, and energy understanding without deploying hardware everywhere. That is exactly where NILM becomes attractive.',
    ],
];

$costBenefits = [
    'Lower hardware cost because the system can start from one mains sensor.',
    'Lower installation effort because you do not need to wire or pair a separate monitor for every appliance.',
    'Better scalability because adding insight for another appliance can come from training, not from buying another device.',
    'Better Home Assistant integration because predictions can become virtual appliance entities used in dashboards and automations.',
    'A realistic tradeoff: lower cost and faster deployment in exchange for estimation instead of direct per-device measurement.',
];

$essentials = [
    'A mains power sensor available in Home Assistant.',
    'The NILM app installed and running.',
    'The NILM Training Server app installed and running if you want training.',
    'Enough history in Home Assistant for the interval you plan to analyze or train on.',
];

$sections = [
    [
        'id' => 'overview',
        'title' => 'Overview',
        'eyebrow' => 'Getting Started',
        'intro' => 'NILM brings appliance-level visibility to Home Assistant from a single mains power signal. It is designed for users who want more than total consumption, but do not want the cost and complexity of physically metering every appliance.',
        'blocks' => [
            [
                'type' => 'cards',
                'items' => $valueProps,
            ],
            [
                'type' => 'list',
                'title' => 'Typical reasons to use NILM in Home Assistant',
                'items' => $useCases,
            ],
            [
                'type' => 'callout',
                'title' => 'Why this product can be worth installing',
                'body' => 'If you already had dedicated metering for every appliance, you would not need NILM. The reason to use NILM is that full ILM-style instrumentation is expensive, time-consuming, and often unrealistic for an existing home. NILM gives you a lower-cost path to appliance-level insight by reusing a mains signal you may already have in Home Assistant. Once a trained model is useful enough, NILM can also expose live appliance entities inside Home Assistant for dashboards, automations, and energy workflows.',
            ],
            [
                'type' => 'list',
                'title' => 'Documentation order',
                'items' => [
                    'Start with Installation And First Setup to get both apps running correctly.',
                    'Continue with How to train your first appliance to create your first model.',
                    'Use Energy Dashboard to validate models and inspect predictions on historical ranges.',
                    'Check Live Entities In Home Assistant when you are ready to publish models for daily use.',
                    'Use Troubleshooting And Practical Tips whenever behavior does not match expectations.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Before you begin',
                'items' => $essentials,
            ],
            [
                'type' => 'list',
                'title' => 'What NILM means',
                'items' => $whatNilmMeans,
            ],
            [
                'type' => 'cards',
                'title' => 'ILM vs NILM',
                'items' => $ilmVsNilm,
            ],
            [
                'type' => 'list',
                'title' => 'How this product works in practice',
                'items' => $howItWorks,
            ],
            [
                'type' => 'list',
                'title' => 'Why a Home Assistant user would want this',
                'items' => [
                    'You can estimate appliance activity without putting a separate plug or meter on every device.',
                    'You can train models from your own home data instead of relying only on generic assumptions.',
                    'You can preview and validate a model before exposing it as a live entity in Home Assistant.',
                    'You can turn raw mains power into appliance-level signals that are more useful for automations and energy understanding.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Cost and benefit tradeoff',
                'items' => $costBenefits,
            ],
            [
                'type' => 'callout',
                'title' => 'Important expectation',
                'body' => 'NILM is designed to give useful appliance-level insight from one mains signal, not to replace a full hardware submetering setup. Its value is in practical visibility, validation, and automation support with much lower instrumentation effort.',
            ],
            [
                'type' => 'cards',
                'items' => [
                    [
                        'title' => 'NILM',
                        'body' => 'The main app inside Home Assistant. It reads one mains sensor, stores appliance models, shows the Energy Dashboard, exposes the Appliance Training Session page, and can publish live entities back into Home Assistant.',
                    ],
                    [
                        'title' => 'NILM Training Server',
                        'body' => 'The companion training app. It receives prepared jobs from NILM, runs the training process in the background, and returns the trained appliance model with deployment metadata.',
                    ],
                    [
                        'title' => 'Typical Flow',
                        'body' => 'Install both apps, connect the training server, configure the mains sensor, train one or more appliance models, preview them in the dashboard, and enable live publishing for the models you want in Home Assistant.',
                    ],
                ],
            ],
            [
                'type' => 'list',
                'title' => 'What the user can do with the apps',
                'items' => [
                    'Monitor one aggregate mains power sensor.',
                    'Train appliance models from Home Assistant history.',
                    'Preview single or multiple appliance disaggregation results on historical ranges.',
                    'Inspect appliance on/off probability and threshold behavior directly in the dashboard.',
                    'Publish appliance power and on/off entities back into Home Assistant.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'What to expect from results',
                'items' => $expectations,
            ],
        ],
    ],
    [
        'id' => 'installation',
        'title' => 'Installation And First Setup',
        'eyebrow' => 'Setup',
        'intro' => 'This is the recommended first-time setup flow for a Home Assistant user.',
        'blocks' => [
            [
                'type' => 'steps',
                'title' => 'Add the repository and install the apps',
                'items' => [
                    'Open Home Assistant and go to Settings.',
                    'Open Apps, then App Store.',
                    'Open the top-right menu and choose Repositories.',
                    'Add this repository URL: https://github.com/lgarciamarrero92/ha-nilm',
                    'Install both apps: NILM and NILM Training Server.',
                ],
            ],
            [
                'type' => 'steps',
                'title' => 'Start the apps in the correct order',
                'items' => [
                    'Start NILM Training Server first.',
                    'Then start the NILM app.',
                    'Open the NILM web UI from Home Assistant.',
                ],
            ],
            [
                'type' => 'callout',
                'title' => 'Important',
                'body' => 'The training server should be running before you begin training appliances. NILM can still open without it, but training will not work until the server is selected and saved.',
            ],
            [
                'type' => 'steps',
                'title' => 'Complete the initial NILM setup',
                'items' => [
                    'Open Appliance Training Session and look for the Training Server Connection card.',
                    'If the internal training app is detected, select it and press Save.',
                    'Open Energy Dashboard.',
                    'Choose the aggregate mains power sensor you want NILM to monitor.',
                    'Wait for the dashboard to save the sensor automatically and load the mains chart.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Before moving on, confirm all of these',
                'items' => [
                    'NILM is running.',
                    'NILM Training Server is running.',
                    'The training server is selected and saved in Appliance Training Session.',
                    'The mains sensor is selected in Energy Dashboard.',
                    'The mains chart loads correctly.',
                ],
            ],
        ],
    ],
    [
        'id' => 'energy-dashboard',
        'title' => 'Energy Dashboard',
        'eyebrow' => 'Visualization And Preview',
        'intro' => 'Energy Dashboard is the main operational page of the NILM app. It combines configuration, visualization, preview, and model management.',
        'blocks' => [
            [
                'type' => 'cards',
                'items' => [
                    [
                        'title' => 'Mains Signal',
                        'body' => 'Choose the mains sensor, select a history range, and inspect the mains chart. The chart supports zoom, pan, and touch interaction on mobile.',
                    ],
                    [
                        'title' => 'Appliance Models',
                        'body' => 'Review all trained appliance models stored in NILM. Each card shows the appliance name, training quality, live publishing state, and a Disaggregate action.',
                    ],
                    [
                        'title' => 'Preview Area',
                        'body' => 'Predicted appliance lines are drawn directly on top of the mains chart. Multiple predictions can be shown at once and removed individually with the chips below the chart.',
                    ],
                ],
            ],
            [
                'type' => 'list',
                'title' => 'What you can do in Energy Dashboard',
                'items' => [
                    'Select and save the mains sensor.',
                    'Inspect recent mains history on an interactive chart.',
                    'Preview a single appliance with Disaggregate.',
                    'Preview all available models with Disaggregate All.',
                    'Enable or disable live publishing per appliance model.',
                    'Inspect tooltips with appliance power, ON/OFF state, probability p, and threshold thr.',
                ],
            ],
            [
                'type' => 'steps',
                'title' => 'Preview one appliance',
                'items' => [
                    'Load the time range you want to analyze.',
                    'Find the appliance model card in Appliance Models.',
                    'Click Disaggregate.',
                    'Wait for the prediction progress to finish.',
                    'Inspect the predicted appliance line on top of the mains chart.',
                    'Hover the line to inspect power, ON/OFF state, p, and thr.',
                ],
            ],
            [
                'type' => 'steps',
                'title' => 'Preview all appliances',
                'items' => [
                    'Load the time range you want to analyze.',
                    'Click Disaggregate All in the Models header area.',
                    'Wait for all predictions to be computed.',
                    'Review the chart, the prediction chips, and the appliance share diagram.',
                ],
            ],
            [
                'type' => 'callout',
                'title' => 'Performance note',
                'body' => 'Disaggregate All is heavier than a single-appliance preview because it creates and transfers multiple prediction series at once. It is best used for overview, while single-appliance preview is better for detailed debugging.',
            ],
            [
                'type' => 'list',
                'title' => 'Appliance share diagram',
                'items' => [
                    'Shows the contribution of the currently plotted appliance predictions.',
                    'Includes Base Load, which represents always-on or background consumption.',
                    'Includes Other, which is the unexplained part of the mains not covered by the plotted appliances and base load.',
                    'Updates dynamically when a prediction is added or removed.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Mobile behavior',
                'items' => [
                    'The chart supports touch interaction.',
                    'The app scrolls back to the chart automatically after a prediction starts.',
                    'Stats stay in a compact two-column layout on phones.',
                    'The models summary and controls use a mobile-friendly full-width layout.',
                ],
            ],
        ],
    ],
    [
        'id' => 'training',
        'title' => 'How to train your first appliance',
        'eyebrow' => 'Model Training',
        'intro' => 'Appliance Training Session is the page used to prepare training data from Home Assistant history and send the job to the training server.',
        'blocks' => [
            [
                'type' => 'list',
                'title' => 'What this page covers',
                'items' => [
                    'Training server selection and validation.',
                    'Appliance name selection.',
                    'Supervision mode selection.',
                    'History range selection.',
                    'Training data preparation.',
                    'Job upload and progress tracking.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Training stepper',
                'items' => [
                    'Server',
                    'Appliance',
                    'Labels',
                    'Prepare',
                    'Train',
                ],
            ],
            [
                'type' => 'steps',
                'title' => 'Training server connection',
                'items' => [
                    'Open the Training Server Connection card.',
                    'Confirm that the desired training server is detected or available.',
                    'Select the server.',
                    'Press Save.',
                    'Make sure the card shows the server as ready before continuing.',
                ],
            ],
            [
                'type' => 'cards',
                'items' => [
                    [
                        'title' => 'Interval Supervision',
                        'body' => 'Use this mode when you do not have a dedicated appliance sensor. You manually define ON intervals from the mains signal.',
                    ],
                    [
                        'title' => 'Ground-Truth Appliance Sensor',
                        'body' => 'Use this mode when you already have a Home Assistant sensor for the appliance. NILM derives the ON intervals from that sensor.',
                    ],
                ],
            ],
            [
                'type' => 'callout',
                'title' => 'Exact sensor-debug behavior',
                'body' => 'In ground-truth sensor mode, the ON intervals shown in the chart now use the exact backend Python logic used to prepare the training labels. This makes the training chart suitable for debugging sensor-derived labels.',
            ],
            [
                'type' => 'list',
                'title' => 'Sensor-derived ON interval logic',
                'items' => [
                    'The appliance sensor is aligned to the training grid.',
                    'A sensor-derived ON mask is built from that aligned signal.',
                    'Short OFF gaps are bridged first.',
                    'Short ON runs are removed after that.',
                ],
            ],
            [
                'type' => 'steps',
                'title' => 'Prepare and send a training job',
                'items' => [
                    'Choose the appliance name.',
                    'Choose the supervision mode.',
                    'Choose the history range.',
                    'If needed, add manual intervals or select a ground-truth appliance sensor.',
                    'Prepare the training data.',
                    'Send the job to the training server.',
                    'Wait for the job to finish and for the new model to appear in Energy Dashboard.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'What preparation does',
                'items' => [
                    'Fetches the relevant mains history.',
                    'Aligns the signal to the model sampling grid.',
                    'Builds the model input windows.',
                    'Filters invalid windows.',
                    'Extracts the embeddings used for training.',
                    'Creates the target labels.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'After training completes',
                'items' => [
                    'The appliance model is stored inside NILM.',
                    'Deployment metrics are computed for the model.',
                    'The deployed ON/OFF threshold is derived from the edge runtime replay.',
                    'The model becomes available in Energy Dashboard.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Good training practices',
                'items' => [
                    'Use clear appliance names such as fridge, electric_oven, or dishwasher.',
                    'Start with a focused history range instead of a very long noisy range.',
                    'Prefer sensor supervision when a good appliance sensor exists.',
                    'Use interval supervision when manual control is more reliable.',
                    'After training, preview the same interval in Energy Dashboard to validate the model.',
                ],
            ],
        ],
    ],
    [
        'id' => 'entities',
        'title' => 'Live Entities In Home Assistant',
        'eyebrow' => 'Published Results',
        'intro' => 'Once appliance models are trained and live publishing is enabled, NILM creates live Home Assistant entities for those appliances.',
        'blocks' => [
            [
                'type' => 'list',
                'title' => 'Entities created by NILM',
                'items' => [
                    'sensor.nilm_<appliance>_power',
                    'binary_sensor.nilm_<appliance>_on',
                    'sensor.nilm_disaggregation_duration',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Useful entity attributes',
                'items' => [
                    'The live ON/OFF probability.',
                    'The deployed ON/OFF threshold used by the model.',
                    'The power sensor and binary sensor use the saved model threshold, not a fixed 0.5 threshold.',
                ],
            ],
            [
                'type' => 'callout',
                'title' => 'Why this matters',
                'body' => 'If the live binary state looks surprising, inspect the entity attributes in Home Assistant. They allow you to check whether the appliance is OFF because the probability is low or because the deployed threshold is strict.',
            ],
        ],
    ],
    [
        'id' => 'troubleshooting',
        'title' => 'Troubleshooting And Practical Tips',
        'eyebrow' => 'Support',
        'intro' => 'These are the most useful checks when something does not behave as expected.',
        'blocks' => [
            [
                'type' => 'faq',
                'items' => [
                    [
                        'question' => 'The training server is detected but training still does not work.',
                        'answer' => 'Detection alone is not enough. The training server must still be selected in the Training Server Connection card and then saved before NILM uses it.',
                    ],
                    [
                        'question' => 'The upload to the training server failed.',
                        'answer' => 'Check that NILM Training Server is running, that the Training Server Connection card shows the server as ready, and that the selected history range is not unnecessarily large.',
                    ],
                    [
                        'question' => 'A new model appears, but the preview quality looks weak.',
                        'answer' => 'Preview the model on the same interval used for training. Inspect the dashboard tooltip values for power, ON/OFF state, p, and thr. This usually shows whether the model is too conservative, too noisy, or simply using a strict threshold.',
                    ],
                    [
                        'question' => 'The ground-truth appliance sensor intervals look strange.',
                        'answer' => 'The displayed raw appliance sensor line and the derived ON intervals are not the same thing. The intervals come from the backend training-label logic, which can bridge short OFF gaps and then remove short ON runs.',
                    ],
                    [
                        'question' => 'Disaggregate All seems much heavier than previewing a single appliance.',
                        'answer' => 'That is expected. Disaggregate All computes and transfers multiple prediction series at once. It is useful for overview, but single-appliance preview is usually better for detailed debugging and lower memory usage.',
                    ],
                    [
                        'question' => 'The frontend still looks stale after an update.',
                        'answer' => 'Home Assistant can cache frontend assets aggressively. Reload the page, try a hard refresh, close and reopen the app page, or clear the Home Assistant site data in the browser if necessary.',
                    ],
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Practical advice',
                'items' => [
                    'Start by training one appliance with a distinctive signature.',
                    'Use a mains sensor with regular updates and sufficient history.',
                    'Prefer single-appliance preview when debugging.',
                    'Use Disaggregate All for overview, not for the most precise inspection.',
                    'Compare a model on the same interval used for training whenever you need to validate it.',
                ],
            ],
        ],
    ],
];

$sectionOrder = [
    'overview',
    'installation',
    'training',
    'energy-dashboard',
    'entities',
    'troubleshooting',
];

$sectionsById = [];
foreach ($sections as $section) {
    $sectionsById[$section['id']] = $section;
}

function render_block(array $block): void
{
    $type = $block['type'] ?? '';

    if (!empty($block['title'])) {
        echo '<h3>' . htmlspecialchars($block['title']) . '</h3>';
    }

    if ($type === 'cards') {
        echo '<div class="card-grid">';
        foreach ($block['items'] as $item) {
            echo '<article class="info-card">';
            echo '<h4>' . htmlspecialchars($item['title']) . '</h4>';
            echo '<p>' . htmlspecialchars($item['body']) . '</p>';
            echo '</article>';
        }
        echo '</div>';
        return;
    }

    if ($type === 'steps') {
        echo '<ol class="step-list">';
        foreach ($block['items'] as $item) {
            echo '<li>' . htmlspecialchars($item) . '</li>';
        }
        echo '</ol>';
        return;
    }

    if ($type === 'list') {
        echo '<ul class="bullet-list">';
        foreach ($block['items'] as $item) {
            echo '<li>' . htmlspecialchars($item) . '</li>';
        }
        echo '</ul>';
        return;
    }

    if ($type === 'callout') {
        echo '<div class="callout">';
        echo '<strong>' . htmlspecialchars($block['title']) . '</strong>';
        echo '<p>' . htmlspecialchars($block['body']) . '</p>';
        echo '</div>';
        return;
    }

    if ($type === 'faq') {
        echo '<div class="faq-list">';
        foreach ($block['items'] as $item) {
            echo '<details class="faq-item">';
            echo '<summary>' . htmlspecialchars($item['question']) . '</summary>';
            echo '<p>' . htmlspecialchars($item['answer']) . '</p>';
            echo '</details>';
        }
        echo '</div>';
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Non-Intrusive Load Monitoring for Home Assistant</title>
    <meta name="description" content="Documentation for Non-Intrusive Load Monitoring for Home Assistant, including installation, appliance training, energy dashboard usage, live entities, and troubleshooting.">
    <link rel="stylesheet" href="./assets/docs.css">
</head>
<body>
    <div class="site-shell">
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-inner">
                <div class="brand">
                    <h1>NILM</h1>
                    <p>Non-Intrusive Load Monitoring for Home Assistant. Documentation for the NILM apps for Home Assistant.</p>
                </div>

                <nav class="toc" aria-label="Documentation sections">
                    <?php foreach ($sectionOrder as $sectionId):
                        $section = $sectionsById[$sectionId] ?? null;
                        if (!$section) {
                            continue;
                        }
                    ?>
                        <a href="#<?= htmlspecialchars($section['id']) ?>"><?= htmlspecialchars($section['title']) ?></a>
                    <?php endforeach; ?>
                </nav>
            </div>
        </aside>

        <main class="content">
            <header class="hero">
                <button class="nav-toggle" id="navToggle" type="button" aria-expanded="false" aria-controls="sidebar">Menu</button>
                <h2>Non-Intrusive Load Monitoring for Home Assistant</h2>
                <p>
                    NILM helps you move from one aggregate mains signal to appliance-level insight.
                    Instead of seeing only total consumption, you can estimate which appliances are active,
                    preview their behavior on historical ranges, and publish virtual appliance entities back
                    into Home Assistant without deploying dedicated hardware on every device.
                </p>

                <div class="hero-links">
                    <a href="<?= htmlspecialchars($githubRepoUrl) ?>" class="product-link" target="_blank" rel="noopener noreferrer" data-track="cta" data-track-label="Hero GitHub">
                        <span class="product-link-icon" aria-hidden="true">
                            <svg viewBox="0 0 24 24" role="img" focusable="false">
                                <path d="M12 2C6.48 2 2 6.58 2 12.23c0 4.52 2.87 8.35 6.84 9.71.5.1.68-.22.68-.49 0-.24-.01-1.04-.01-1.88-2.78.62-3.37-1.21-3.37-1.21-.45-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.63.07-.63 1 .08 1.53 1.06 1.53 1.06.9 1.57 2.36 1.12 2.94.86.09-.67.35-1.12.64-1.38-2.22-.26-4.56-1.14-4.56-5.09 0-1.13.39-2.06 1.03-2.79-.1-.26-.45-1.31.1-2.74 0 0 .84-.28 2.75 1.07A9.3 9.3 0 0 1 12 6.84c.85 0 1.71.12 2.52.35 1.91-1.35 2.75-1.07 2.75-1.07.55 1.43.2 2.48.1 2.74.64.73 1.03 1.66 1.03 2.79 0 3.96-2.34 4.83-4.57 5.08.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .27.18.59.69.49A10.27 10.27 0 0 0 22 12.23C22 6.58 17.52 2 12 2Z" fill="currentColor"/>
                            </svg>
                        </span>
                        <span>
                            <strong>GitHub Repository</strong>
                            <small>View source code, releases, and project details</small>
                        </span>
                    </a>

                    <a href="<?= htmlspecialchars($haAddRepositoryUrl) ?>" class="product-link" target="_blank" rel="noopener noreferrer" data-track="cta" data-track-label="Hero Add Repository">
                        <span class="product-link-icon" aria-hidden="true">
                            <svg viewBox="0 0 24 24" role="img" focusable="false">
                                <path d="M12 2.5 4 6.6v5.96c0 4.62 3.2 8.92 8 9.94 4.8-1.02 8-5.32 8-9.94V6.6l-8-4.1Zm0 2.02 5.9 3.02-2.24 1.14-3.66-1.88-3.66 1.88L6.1 7.54 12 4.52Zm-6 4.64 5 2.56v8.35c-3.04-.95-5-3.98-5-7.51V9.16Zm7 10.91v-8.35l5-2.56v3.4c0 3.53-1.96 6.56-5 7.51Z" fill="currentColor"/>
                            </svg>
                        </span>
                        <span>
                            <strong>Install In Home Assistant</strong>
                            <small>Add this repository directly to your Home Assistant app store</small>
                        </span>
                    </a>
                </div>

            </header>

            <?php foreach ($sectionOrder as $sectionId):
                $section = $sectionsById[$sectionId] ?? null;
                if (!$section) {
                    continue;
                }
            ?>
                <section id="<?= htmlspecialchars($section['id']) ?>" class="doc-section">
                    <div class="section-head">
                        <span class="eyebrow"><?= htmlspecialchars($section['eyebrow']) ?></span>
                        <h2><?= htmlspecialchars($section['title']) ?></h2>
                        <p><?= htmlspecialchars($section['intro']) ?></p>
                    </div>

                    <div class="section-body">
                        <?php foreach ($section['blocks'] as $block) {
                            render_block($block);
                        } ?>
                    </div>
                </section>
            <?php endforeach; ?>

            <footer class="site-footer">
                <div>
                    <strong>NILM documentation</strong>
                    <p>Written for real Home Assistant usage: setup, training, preview, live publishing, and troubleshooting.</p>
                </div>
                <div class="footer-links">
                    <a href="#installation" data-track="cta" data-track-label="Footer installation">Installation</a>
                    <a href="#energy-dashboard" data-track="cta" data-track-label="Footer dashboard">Energy Dashboard</a>
                    <a href="#training" data-track="cta" data-track-label="Footer training">Training</a>
                    <a href="./stats.php" data-track="cta" data-track-label="Footer stats">Usage Stats</a>
                    <button type="button" class="link-button" id="manageConsentBtn">Analytics Preferences</button>
                </div>
            </footer>
        </main>
    </div>

    <div class="consent-banner" id="consentBanner" hidden>
        <div class="consent-content">
            <div>
                <span class="eyebrow">Privacy</span>
                <h3>Analytics consent</h3>
                <p>
                    This documentation site can collect privacy-friendly usage analytics such as page views,
                    section views, CTA clicks, and scroll depth to help evaluate interest in the NILM apps.
                    No analytics data is sent unless you explicitly accept.
                </p>
            </div>
            <div class="consent-actions">
                <button type="button" class="button secondary consent-btn" id="rejectConsentBtn">Reject</button>
                <button type="button" class="button primary consent-btn" id="acceptConsentBtn">Accept analytics</button>
            </div>
        </div>
    </div>

    <script src="./assets/docs.js"></script>
</body>
</html>

