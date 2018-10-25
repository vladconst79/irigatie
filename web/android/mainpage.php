<?php
include('header.php');
$conn = mysqli_connect($ini_array['DB_SERVER'], $ini_array['DB_USER'], $ini_array['DB_PASS'],$ini_array['DB_NAME']);
if (mysqli_connect_errno()) {
    print(json_encode("Eroare"));
}
if (empty($_POST)) {
    $sql = "SELECT trasee.denumire, trasee.id AS tid, programari.* FROM programari LEFT JOIN trasee ON programari.traseu_id = trasee.id;";
    $result = mysqli_query($conn, $sql);
    $rows = mysqli_fetch_all($result, MYSQLI_ASSOC);
    print(json_encode($rows));
    mysqli_free_result($result);
}
if (isset($_POST['insert'])) {
    $stmt = mysqli_prepare($conn, "INSERT INTO programari (traseu_id, h, m, dom, mon, dow, durata, max_ploaie) VALUES (?, ?, ?, ?, ?, ?, ?, ?);");
    if (!$stmt) {
        die ("<pre style='color:#EE2711'>Failed to connect to MySQL: {".mysqli_error($conn)."}</pre>");
    }
    mysqli_stmt_bind_param($stmt, "isssssii", $_POST['traseu'], $_POST['h'], $_POST['m'], $_POST['dom'], $_POST['mon'], $_POST['dow'], $_POST['durata'], $_POST['max_ploaie']);
    mysqli_stmt_execute($stmt);
    mysqli_stmt_close($stmt);
    if (file_exists('/tmp/crontab.txt')) unlink('/tmp/crontab.txt');
    $result = mysqli_query($conn, 'SELECT * FROM programari;');
    while ($row = mysqli_fetch_array($result, MYSQLI_ASSOC)) {
        file_put_contents('/tmp/crontab.txt', $row['m'].' '.$row['h'].' '.$row['dom'].' '.$row['mon'].' '.$row['dom'].' /home/pi/irigatie/client.py -c START -p '.$row['traseu_id'].PHP_EOL, FILE_APPEND);
    }
    mysqli_free_result($result);
    shell_exec('crontab -r');
    shell_exec('crontab /tmp/crontab.txt');
    unset($_POST);
    print(json_encode("OK"));
}
if (isset($_POST['edex'])) {
    $stmt = mysqli_prepare($conn, "UPDATE programari SET traseu_id = ?, h = ?, m = ?, dom = ?, mon = ?, dow = ?, durata = ?, max_ploaie = ? WHERE id = ?;");
    if (!$stmt) {
        die ("<pre style='color:#EE2711'>Failed to connect to MySQL: {".mysqli_error($conn)."}</pre>");
    }
    mysqli_stmt_bind_param($stmt, "isssssiii", $_POST['traseu'], $_POST['h'], $_POST['m'], $_POST['dom'], $_POST['mon'], $_POST['dow'], $_POST['durata'], $_POST['max_ploaie'], $_POST['edex']);
    mysqli_stmt_execute($stmt);
    mysqli_stmt_close($stmt);
    if (file_exists('/tmp/crontab.txt')) unlink('/tmp/crontab.txt');
    $result = mysqli_query($conn, 'SELECT * FROM programari;');
    while ($row = mysqli_fetch_array($result, MYSQLI_ASSOC)) {
        file_put_contents('/tmp/crontab.txt', $row['m'].' '.$row['h'].' '.$row['dom'].' '.$row['mon'].' '.$row['dom'].' /home/pi/irigatie/client.py -c START -p '.$row['traseu_id'].PHP_EOL, FILE_APPEND);
    }
    mysqli_free_result($result);
    shell_exec('crontab -r');
    shell_exec('crontab /tmp/crontab.txt');
    unset($_POST);
    print(json_encode("OK"));
}
if (isset($_POST['execute'])) {
    $sock = socket_create(AF_UNIX, SOCK_DGRAM, 0);
    socket_sendto($sock,'START ' . $_POST['execute'], 7, 0, '/tmp/python_irigatie_unix_socket', 0);
    print(json_encode("OK"));
}

mysqli_close($conn);