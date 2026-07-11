<?php
include('header.php');
$conn = mysqli_connect($ini_array['DB_SERVER'], $ini_array['DB_USER'], $ini_array['DB_PASS'],$ini_array['DB_NAME']);
if (mysqli_connect_errno()) {
    print(json_encode("Eroare"));
}
if (empty($_POST)) {
    $sql = "SELECT * FROM trasee;";
    $result = mysqli_query($conn, $sql);
    $rows = mysqli_fetch_all($result, MYSQLI_ASSOC);
    print(json_encode($rows));
    mysqli_free_result($result);
}
if (isset($_POST['edex'])) {
    if (isset($_POST['activ'])) {
        $activ = 1;
    } else {
        $activ = 0;
    }
    $stmt = mysqli_prepare($conn, "UPDATE trasee SET denumire = ?, tip = ?, activ = ? WHERE id = ?;");
    if (!$stmt) {
        print(json_encode("Eroare"));
    }
    mysqli_stmt_bind_param($stmt, "siii", $_POST['denumire'], $_POST['tip'], $activ, $_POST['edex']);
    mysqli_stmt_execute($stmt);
    mysqli_stmt_close($stmt);
    unset($_POST);
    print(json_encode("OK"));
}
mysqli_close($conn);