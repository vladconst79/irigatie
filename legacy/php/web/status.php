<?php
include('header.php');

function status_h($value) {
    return htmlspecialchars((string)$value, ENT_QUOTES, 'UTF-8');
}

function status_value($value) {
    if ($value === null) {
        return '<span class="text-muted">N/A</span>';
    }
    if ($value === true) {
        return '<span class="label label-success">true</span>';
    }
    if ($value === false) {
        return '<span class="label label-default">false</span>';
    }
    if (is_array($value)) {
        return status_h(json_encode($value));
    }
    return status_h($value);
}

function status_badge($state, $ok_states = array('idle', 'running')) {
    $state = (string)$state;
    $class = in_array($state, $ok_states) ? 'label-success' : 'label-warning';
    if ($state === 'error' || $state === 'interrupted') {
        $class = 'label-danger';
    }
    return '<span class="label ' . $class . '">' . status_h($state) . '</span>';
}

function status_table($title, $rows) {
    echo '<div class="panel panel-default">';
    echo '<div class="panel-heading"><strong>' . status_h($title) . '</strong></div>';
    echo '<table class="table table-condensed table-striped" style="margin-bottom: 0">';
    foreach ($rows as $label => $value) {
        echo '<tr><th style="width: 240px">' . status_h($label) . '</th><td>' . $value . '</td></tr>';
    }
    echo '</table></div>';
}

$status = irigatie_controller_status($ini_array);
$gateway = isset($status['gateway']) && is_array($status['gateway']) ? $status['gateway'] : array();
$daemon = isset($status['daemon']) && is_array($status['daemon']) ? $status['daemon'] : array();
$runtime = isset($daemon['runtime']) && is_array($daemon['runtime']) ? $daemon['runtime'] : array();
$db = isset($daemon['db']) && is_array($daemon['db']) ? $daemon['db'] : array();
$queue = isset($daemon['queue']) && is_array($daemon['queue']) ? $daemon['queue'] : array();
$last_rain = isset($daemon['last_rain_update']) && is_array($daemon['last_rain_update']) ? $daemon['last_rain_update'] : array();
$relays = isset($daemon['relay_state']) && is_array($daemon['relay_state']) ? $daemon['relay_state'] : array();
?>

<div class="container" id="status" style="margin-left: 20px; max-width: 1180px">
    <div class="row" style="margin-top: 20px; margin-bottom: 12px">
        <div class="col-md-9">
            <h3 style="margin-top: 0">Status irigatie</h3>
        </div>
        <div class="col-md-3" style="text-align: right">
            <a href="status.php" class="btn btn-default">Refresh</a>
        </div>
    </div>

    <?php if (empty($status['ok'])) { ?>
        <div class="alert alert-warning">
            <strong>Status incomplet.</strong>
            <?php echo status_h(isset($status['error']) ? $status['error'] : 'Controller API did not report ok.'); ?>
            <?php if (isset($status['http_status'])) { ?>
                HTTP <?php echo status_h($status['http_status']); ?>.
            <?php } ?>
        </div>
    <?php } ?>

    <?php
    status_table('Daemon', array(
        'State' => status_badge(isset($daemon['daemon_state']) ? $daemon['daemon_state'] : 'unknown'),
        'Program curent' => status_value(isset($daemon['current_program']) ? $daemon['current_program'] : null),
        'Traseu curent' => status_value(isset($daemon['current_zone']) ? $daemon['current_zone'] : null),
        'Secunde ramase' => status_value(isset($daemon['remaining_seconds']) ? $daemon['remaining_seconds'] : null),
        'Mesaj runtime' => status_value(isset($runtime['message']) ? $runtime['message'] : null),
        'Heartbeat' => status_value(isset($runtime['heartbeat_at']) ? $runtime['heartbeat_at'] : null),
    ));

    status_table('Gateway', array(
        'State' => status_badge(isset($gateway['state']) ? $gateway['state'] : 'unknown', array('running')),
        'Socket path' => status_value(isset($gateway['socket_path']) ? $gateway['socket_path'] : null),
        'Socket exista' => status_value(isset($gateway['socket_exists']) ? $gateway['socket_exists'] : null),
        'Daemon STATUS' => status_value(isset($gateway['daemon_status_supported']) ? $gateway['daemon_status_supported'] : null),
    ));

    status_table('Database si coada', array(
        'DB ok' => status_value(isset($db['ok']) ? $db['ok'] : null),
        'DB error' => status_value(isset($db['error']) ? $db['error'] : null),
        'Comenzi asteptare' => status_value(isset($queue['pending_watering_commands']) ? $queue['pending_watering_commands'] : null),
        'Max asteptare' => status_value(isset($queue['max_pending_watering_commands']) ? $queue['max_pending_watering_commands'] : null),
    ));

    status_table('Ultima ploaie', array(
        'Sursa' => status_value(isset($last_rain['source']) ? $last_rain['source'] : null),
        'Moment' => status_value(isset($last_rain['event_time']) ? $last_rain['event_time'] : null),
        'Cantitate mm' => status_value(isset($last_rain['amount_mm']) ? $last_rain['amount_mm'] : null),
        'Raw' => status_value(isset($last_rain['raw_value']) ? $last_rain['raw_value'] : null),
    ));
    ?>

    <div class="panel panel-default">
        <div class="panel-heading"><strong>Relee</strong></div>
        <table class="table table-condensed table-striped" style="margin-bottom: 0">
            <thead>
            <tr>
                <th>Releu</th>
                <th>Stare</th>
            </tr>
            </thead>
            <tbody>
            <?php if (empty($relays)) { ?>
                <tr><td colspan="2"><span class="text-muted">N/A</span></td></tr>
            <?php } else { ?>
                <?php foreach ($relays as $name => $state) { ?>
                    <tr>
                        <th><?php echo status_h($name); ?></th>
                        <td><?php echo status_value($state); ?></td>
                    </tr>
                <?php } ?>
            <?php } ?>
            </tbody>
        </table>
    </div>
</div>
