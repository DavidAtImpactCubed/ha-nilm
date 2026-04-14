<?php
$githubRepoUrl = 'https://github.com/lgarciamarrero92/ha-nilm';
$haAddRepositoryUrl = 'https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Flgarciamarrero92%2Fha-nilm';
$haLogoUrl = './assets/home-assistant-logo.svg';

$sections = [
    [
        'id' => 'overview',
        'title' => 'Overview',
        'eyebrow' => 'Introduction',
        'intro' => 'Non-Intrusive Load Monitoring, or NILM, estimates appliance-level behavior from one aggregate mains power signal. This project brings that workflow into Home Assistant through two apps: NILM, which handles visualization, model storage, and live publishing, and NILM Training Server, which handles training. The practical purpose is to give the user appliance-level visibility with far less hardware than a full intrusive monitoring setup.',
        'blocks' => [
            [
                'type' => 'cards',
                'title' => 'ILM and NILM',
                'items' => [
                    [
                        'title' => 'ILM: Intrusive Load Monitoring',
                        'body' => 'ILM measures appliances directly with hardware such as smart plugs, clamp meters, or submeters. It is usually easier to trust, but hardware cost and installation effort increase with every additional appliance you want to monitor.',
                    ],
                    [
                        'title' => 'NILM: Non-Intrusive Load Monitoring',
                        'body' => 'NILM reuses one aggregate mains signal and an appliance model to estimate appliance power and appliance ON/OFF state. It is cheaper and easier to scale than ILM, but the result is an inference, not a direct measurement.',
                    ],
                    [
                        'title' => 'Why the tradeoff matters',
                        'body' => 'For many Home Assistant users, full hardware submetering is too expensive or too invasive. NILM is valuable because it offers useful appliance-level insight without requiring a dedicated physical meter for every device.',
                    ],
                ],
            ],
            [
                'type' => 'list',
                'title' => 'What this project gives you',
                'items' => [
                    'A way to train appliance models from Home Assistant history.',
                    'A dashboard for offline disaggregation on historical intervals.',
                    'A debugging view for power, ON/OFF state, probability p, and threshold thr.',
                    'Live Home Assistant entities for appliance power and appliance ON/OFF state once a model is published.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'What to expect',
                'items' => [
                    'The output is a model estimate derived from mains power, not a direct appliance measurement.',
                    'Some appliances are easier than others because their signatures are more distinctive.',
                    'Model quality depends strongly on signal quality and on how well the training interval represents the appliance behavior.',
                    'The main benefit is lower cost and lower installation effort compared with direct hardware metering.',
                ],
            ],
            [
                'type' => 'callout',
                'title' => 'Reader orientation',
                'body' => 'This documentation is written as a practical technical guide. The title and abstract are at the top of the page, this Overview section acts as the introduction, and the remaining sections follow the operational sequence: quick start, installation, training, dashboard analysis, live entities, and troubleshooting.',
            ],
        ],
    ],
    [
        'id' => 'quick-start',
        'title' => 'Quick Start',
        'eyebrow' => 'Start here',
        'intro' => 'If you want the shortest path to a working model, follow these three steps. The interval workflow now uses weak supervision automatically under the hood, so you can still train from selected ON intervals even when no appliance sensor exists.',
        'blocks' => [
            [
                'type' => 'cards',
                'title' => 'The shortest path',
                'items' => [
                    [
                        'title' => '1. Install both apps',
                        'body' => 'Add the repository, install NILM and NILM Training Server, then start the training server first.',
                    ],
                    [
                        'title' => '2. Pick your supervision style',
                        'body' => 'Use interval supervision when you only know when the appliance was ON. Use sensor supervision when a real appliance power sensor is available.',
                    ],
                    [
                        'title' => '3. Train and validate',
                        'body' => 'Prepare the data, send the job, watch the weak supervision stages in the jobs table, then verify the result on the same interval in Energy Dashboard.',
                    ],
                ],
            ],
            [
                'type' => 'callout',
                'title' => 'What changed recently',
                'body' => 'Interval supervision now feeds a weak mains signal into the trainer. The job runs as a two-stage weak_onoff flow, and the jobs table shows stage 1/2 and stage 2/2 while it runs.',
            ],
        ],
    ],
    [
        'id' => 'installation',
        'title' => 'Installation And First Setup',
        'eyebrow' => 'Section 1',
        'intro' => 'Installation has two objectives: first, make both apps available and running inside Home Assistant; second, select the training server and mains sensor so NILM is ready for training and historical analysis.',
        'blocks' => [
            [
                'type' => 'steps',
                'title' => 'Install the apps',
                'items' => [
                    'Open Home Assistant, go to Settings, then Apps, then App Store.',
                    'Add this repository: https://github.com/lgarciamarrero92/ha-nilm',
                    'Install the NILM app.',
                    'Install the NILM Training Server app.',
                ],
            ],
            [
                'type' => 'steps',
                'title' => 'Start the system',
                'items' => [
                    'Start NILM Training Server first.',
                    'Then start NILM.',
                    'Open the NILM interface from Home Assistant.',
                ],
            ],
            [
                'type' => 'steps',
                'title' => 'Complete the initial configuration',
                'items' => [
                    'Open the training page and select the training server in the Training Server Connection card.',
                    'Open Energy Dashboard and save the mains power sensor.',
                    'Confirm that the mains chart loads and that the training server is reported as ready.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Minimum requirements',
                'items' => [
                    'A mains power sensor must already exist in Home Assistant.',
                    'The NILM app must be running.',
                    'The NILM Training Server app must be running if you plan to train models.',
                    'The Home Assistant recorder must contain enough history for the intervals you want to use.',
                ],
            ],
            [
                'type' => 'callout',
                'title' => 'Important detail',
                'body' => 'Detection is not the same as configuration. The training server can be detected automatically, but it still has to be selected before NILM will use it for training.',
            ],
        ],
    ],
    [
        'id' => 'training',
        'title' => 'How to train your first appliance',
        'eyebrow' => 'Section 2',
        'intro' => 'Training turns historical Home Assistant data into an appliance model. The user defines the appliance, chooses a supervision mode, prepares the data, uploads the job, and then validates the result in Energy Dashboard. Interval training now uses weak supervision automatically behind the scenes.',
        'blocks' => [
            [
                'type' => 'cards',
                'title' => 'Supervision modes',
                'items' => [
                    [
                        'title' => 'Interval supervision',
                        'body' => 'Use this mode when no dedicated appliance sensor exists. You manually mark ON intervals for the target appliance, and NILM derives a weak mains signal and trains in two stages behind the scenes.',
                    ],
                    [
                        'title' => 'Ground-truth appliance sensor',
                        'body' => 'Use this mode when a Home Assistant sensor already exists for the appliance. The backend derives the ON/OFF labels from that sensor and uses those labels for training.',
                    ],
                ],
            ],
            [
                'type' => 'steps',
                'title' => 'Recommended first training workflow',
                'items' => [
                    'Confirm that the training server is selected and ready.',
                    'Choose a clear appliance name.',
                    'Choose the supervision mode.',
                    'Select a focused historical interval that contains representative appliance behavior.',
                    'Prepare the data.',
                    'Send the training job.',
                    'When training completes, validate the model in Energy Dashboard on the same interval.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'What preparation does',
                'items' => [
                    'Fetches mains and supervision data from Home Assistant.',
                    'Aligns the mains signal to the model sampling grid.',
                    'Builds model windows and removes invalid windows caused by data gaps.',
                    'Extracts the embeddings used for appliance training.',
                    'Builds ON/OFF targets for the target appliance.',
                    'When you use interval supervision, also derives a weak mains signal that the trainer uses for the weak_onoff flow.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'What weak supervision does',
                'items' => [
                    'Uses your selected ON intervals as the starting point.',
                    'Builds a weak mains target from the aggregate mains signal by removing the local baseline inside each training window.',
                    'Runs stage 1 to learn a confident classifier embedding.',
                    'Runs stage 2 to train the regression head on pseudo-power together with ON/OFF labels.',
                    'Shows stage 1/2 and stage 2/2 in the training jobs table so you can tell where the job is.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Ground-truth sensor details',
                'items' => [
                    'The chart now shows sensor-derived intervals generated by the exact backend logic used during training preparation.',
                    'The appliance sensor is aligned to the training grid before labels are computed.',
                    'Short OFF gaps are bridged before short ON runs are removed.',
                    'This matters for bursty appliances because nearby short activations can otherwise disappear from the final label mask.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'What happens after training',
                'items' => [
                    'The appliance representation is stored inside NILM.',
                    'Deployment metrics are computed with edge-side replay so the deployed threshold matches runtime behavior.',
                    'The model becomes available in Energy Dashboard.',
                    'The model can later be enabled for live publishing in Home Assistant.',
                ],
            ],
            [
                'type' => 'callout',
                'title' => 'Best first validation',
                'body' => 'The cleanest first validation is to preview the trained appliance on the same interval used for training. That lets you inspect the predicted power, the predicted ON/OFF state, the probability p, and the threshold thr against a range you already understand. For weak supervision jobs, the stage labels in the jobs table help you see whether the trainer is still in the classifier warm-up or has moved to the pseudo-power pass.',
            ],
        ],
    ],
    [
        'id' => 'energy-dashboard',
        'title' => 'Energy Dashboard',
        'eyebrow' => 'Section 3',
        'intro' => 'Energy Dashboard is the historical analysis view of the system. It combines mains visualization, offline disaggregation, model comparison, and publishing controls in a single page.',
        'blocks' => [
            [
                'type' => 'cards',
                'title' => 'Main dashboard elements',
                'items' => [
                    [
                        'title' => 'Mains chart',
                        'body' => 'The mains chart is the reference plot for the selected range. Predictions are drawn on the same chart so the user can compare aggregate power and appliance estimates directly.',
                    ],
                    [
                        'title' => 'Model cards',
                        'body' => 'Each trained appliance appears as a model card with its appliance name, training quality, publishing state, and a Disaggregate action.',
                    ],
                    [
                        'title' => 'Prediction layer',
                        'body' => 'A prediction is added to the existing mains chart, not to a separate modal. Multiple predictions can be displayed at the same time and removed individually.',
                    ],
                ],
            ],
            [
                'type' => 'list',
                'title' => 'What the dashboard is used for',
                'items' => [
                    'Saving the mains power sensor used by NILM.',
                    'Inspecting the historical mains signal.',
                    'Running offline disaggregation for one appliance or for all available models.',
                    'Comparing appliance models before enabling live entities.',
                    'Debugging the relation between predicted power, predicted ON/OFF state, probability p, and threshold thr.',
                ],
            ],
            [
                'type' => 'steps',
                'title' => 'How to validate one appliance',
                'items' => [
                    'Load the interval you want to inspect.',
                    'Click Disaggregate on the target appliance model.',
                    'Wait for the progress overlay to complete.',
                    'Inspect the prediction line on the mains chart.',
                    'Use the tooltip to read power, ON/OFF state, probability p, and threshold thr.',
                ],
            ],
            [
                'type' => 'steps',
                'title' => 'How to inspect the whole interval',
                'items' => [
                    'Load the interval of interest.',
                    'Click Disaggregate All.',
                    'Review the chart, the prediction chips, and the appliance share diagram.',
                    'Remove individual predictions if you want a cleaner comparison.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Appliance share diagram',
                'items' => [
                    'The diagram uses only the predictions that are currently plotted.',
                    'Base Load represents the background part of the mains estimated by the inference logic.',
                    'Other represents the part of the mains not currently explained by the plotted appliances and the estimated base load.',
                    'The diagram updates automatically when predictions are added or removed.',
                ],
            ],
            [
                'type' => 'callout',
                'title' => 'Interpretation note',
                'body' => 'Single-appliance disaggregation is the preferred mode for precise debugging. Disaggregate All is intentionally broader and heavier because it generates several prediction series at once and is meant for overview rather than for the most careful model inspection.',
            ],
        ],
    ],
    [
        'id' => 'entities',
        'title' => 'Live Entities In Home Assistant',
        'eyebrow' => 'Section 4',
        'intro' => 'When live publishing is enabled, NILM creates Home Assistant entities from the trained model. These entities are online model outputs derived from mains power and from the stored appliance representation.',
        'blocks' => [
            [
                'type' => 'list',
                'title' => 'Live entities',
                'items' => [
                    'sensor.nilm_<appliance>_power',
                    'binary_sensor.nilm_<appliance>_on',
                    'sensor.nilm_disaggregation_duration',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'What they mean',
                'items' => [
                    'The power sensor is the estimated appliance power at runtime.',
                    'The binary sensor is the estimated appliance ON/OFF state at runtime.',
                    'The binary decision is based on the model probability and the saved deployed threshold, not on a fixed threshold of 0.5.',
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Useful attributes',
                'items' => [
                    'onoff_score stores the runtime ON/OFF probability.',
                    'onoff_threshold stores the deployed threshold used for the binary decision.',
                    'These attributes are the first place to look when the live binary state seems too conservative or too permissive.',
                ],
            ],
            [
                'type' => 'callout',
                'title' => 'How to interpret live results',
                'body' => 'A live entity should be treated as the online output of the NILM model. It is useful for dashboards and automations, but it remains an estimate inferred from aggregate mains power rather than a direct appliance measurement.',
            ],
        ],
    ],
    [
        'id' => 'troubleshooting',
        'title' => 'Troubleshooting And Practical Tips',
        'eyebrow' => 'Section 5',
        'intro' => 'When the system does not behave as expected, the main task is to determine whether the problem is caused by configuration, training data, model behavior, or interpretation of the output.',
        'blocks' => [
            [
                'type' => 'faq',
                'items' => [
                    [
                        'question' => 'The training server is detected, but training does not work.',
                        'answer' => 'Detection is only discovery. The training server must still be selected in the Training Server Connection card before NILM will use it.',
                    ],
                    [
                        'question' => 'The upload to the training server failed.',
                        'answer' => 'Check that NILM Training Server is running, that the connection card reports it as ready, and that the selected interval is not unnecessarily large for a first test.',
                    ],
                    [
                        'question' => 'A model exists, but the preview looks weak.',
                        'answer' => 'Preview the model on the same interval used during training. Inspect the tooltip values for predicted power, predicted ON/OFF state, probability p, and threshold thr before drawing conclusions from the line shape alone.',
                    ],
                    [
                        'question' => 'The ground-truth intervals look different from the raw appliance sensor line.',
                        'answer' => 'That is expected. The raw line is the aligned display signal, while the intervals come from backend label logic that aligns the sensor, bridges short OFF gaps, and removes short ON runs.',
                    ],
                    [
                        'question' => 'Why does the jobs table show stage 1/2 or stage 2/2 during training?',
                        'answer' => 'That only happens for interval supervision jobs. It means NILM is using the new weak supervision path: stage 1 learns a classifier embedding, and stage 2 trains pseudo-power together with ON/OFF labels.',
                    ],
                    [
                        'question' => 'What is weak supervision in NILM?',
                        'answer' => 'It is the interval-training path used when you only mark ON intervals. The edge app derives a weak mains signal from your selected range, and the trainer uses that signal to guide the regression head without needing a dedicated appliance sensor.',
                    ],
                    [
                        'question' => 'Disaggregate All feels much heavier than disaggregating one appliance.',
                        'answer' => 'That is normal. The all-model path computes and transfers multiple prediction series at once. It is useful for overview, not for the lightest or most focused debugging session.',
                    ],
                    [
                        'question' => 'The frontend still looks stale after an update.',
                        'answer' => 'Home Assistant can cache frontend assets aggressively. Reload the page, try a hard refresh, reopen the app page, or clear the Home Assistant site data if required.',
                    ],
                ],
            ],
            [
                'type' => 'list',
                'title' => 'Practical recommendations',
                'items' => [
                    'Start with one appliance that has a clear signature.',
                    'Prefer single-appliance validation before using Disaggregate All.',
                    'Use the same interval for first-pass training validation whenever possible.',
                    'Use tooltip values, not only visual line shape, when you debug threshold behavior.',
                    'Use NILM when you want useful appliance-level visibility with limited hardware, not when direct legal-grade measurement is mandatory.',
                ],
            ],
        ],
    ],
];

$sectionOrder = [
    'overview',
    'quick-start',
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
    <meta name="description" content="Documentation for Non-Intrusive Load Monitoring for Home Assistant, including quick start, weak interval supervision, installation, appliance training, dashboard analysis, live entities, and troubleshooting.">
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
                    This documentation describes a Home Assistant workflow for appliance-level estimation from one mains power signal.
                    It covers installation, appliance training, historical offline disaggregation, live entity publishing, and practical interpretation of the results.
                    If you only know ON intervals, the latest training flow now uses weak supervision automatically so you can still get a usable model without a dedicated appliance sensor.
                    The goal is to help the user understand when NILM is useful, how to operate the apps correctly, and how to evaluate the quality of a trained appliance model.
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
                            <img src="<?= htmlspecialchars($haLogoUrl) ?>" alt="" class="ha-cta-logo" loading="eager" decoding="async">
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
                    <p>Focused on practical Home Assistant use: setup, training, dashboard analysis, live publishing, and troubleshooting.</p>
                </div>
                <div class="footer-links">
                    <a href="#installation" data-track="cta" data-track-label="Footer installation">Installation</a>
                    <a href="#training" data-track="cta" data-track-label="Footer training">Training</a>
                    <a href="#energy-dashboard" data-track="cta" data-track-label="Footer dashboard">Energy Dashboard</a>
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
