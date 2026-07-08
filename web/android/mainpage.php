<?php
include('header.php');
$conn = mysqli_connect($ini_array['DB_SERVER'], $ini_array['DB_USER'], $ini_array['DB_PASS'],$ini_array['DB_NAME']);
if (mysqli_connect_errno()) {
    print(json_encode("Eroare"));
}
if (empty($_POST)) {
    $sql = "SELECT trasee.denumire, trasee.id AS tid, programari.* FROM programari LEFT JOIN trasee ON programari.traseu_id = trasee.id ORDER BY mon, dom, dow, CAST(SUBSTRING_INDEX(h, ',', 1) AS UNSIGNED), CAST(SUBSTRING_INDEX(m, ',', 1) AS UNSIGNED), trasee.denumire;";
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
    irigatie_controller_reload_schedules($ini_array);
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
    irigatie_controller_reload_schedules($ini_array);
    unset($_POST);
    print(json_encode("OK"));
}
if (isset($_POST['execute'])) {
    irigatie_controller_start($ini_array, $_POST['execute']);
    print(json_encode("OK"));
}

mysqli_close($conn);
