<?php
include('header.php');
$conn = mysqli_connect($ini_array['DB_SERVER'], $ini_array['DB_USER'], $ini_array['DB_PASS'],$ini_array['DB_NAME']);
if (mysqli_connect_errno()) {
    print(json_encode("Eroare"));
}
if (empty($_POST)) {
    $sql = "SELECT * FROM progman ORDER BY id;";
    $result = mysqli_query($conn, $sql);
    $rows = mysqli_fetch_all($result, MYSQLI_ASSOC);
    print(json_encode($rows));
    mysqli_free_result($result);
}
if (isset($_POST['edex'])) {
    $stmt = mysqli_prepare($conn, "UPDATE progman SET denumire = ?, durata_t1 = ?, durata_t2 = ?, durata_t3 = ?, durata_t4 = ? WHERE id = ?;");
    if (!$stmt) {
        die ("<pre style='color:#EE2711'>Failed to connect to MySQL: {".mysqli_error($conn)."}</pre>");
    }
    mysqli_stmt_bind_param($stmt, "siiiii", $_POST['denumire'], $_POST['durata_t1'], $_POST['durata_t2'], $_POST['durata_t3'], $_POST['durata_t4'], $_POST['edex']);
    mysqli_stmt_execute($stmt);
    mysqli_stmt_close($stmt);
    unset($_POST);
    mysqli_close($conn);
    print(json_encode("OK"));
}
if (isset($_POST['execute'])) {
    $sock = socket_create(AF_UNIX, SOCK_DGRAM, 0);
    socket_sendto($sock,'EXEC ' . $_POST['execute'], 6, 0, '/tmp/python_irigatie_unix_socket', 0);
    print(json_encode("OK"));
}
mysqli_close($conn);
