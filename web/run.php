<?php
include('header.php');
$conn = mysqli_connect($ini_array['DB_SERVER'], $ini_array['DB_USER'], $ini_array['DB_PASS'],$ini_array['DB_NAME']);
if (mysqli_connect_errno()) {
    die("<pre style='color:#EE2711'>Failed to connect to MySQL: {".mysqli_connect_error()."}</pre>");
}
?>
<div class="container" id="tables" style="margin-left: 20px">
    <form action="run.php" method="post" id="myForm" onsubmit="window.location.reload()">
        <div class="form-group row">
            <table class="table table-hover" id="myTable" style="white-space: nowrap">
                <thead>
                <th></th>
                <th>DENUMIRE</th>
                <?php
                $sql = "SELECT * FROM trasee ORDER BY id;";
                $result = mysqli_query($conn, $sql);
                $rowz = mysqli_fetch_all($result, MYSQLI_ASSOC);
                foreach ($rowz as $row) {
                    echo "<th style='min-width: 75px'>".$row['denumire']."</th>";
                }
                mysqli_free_result($result);
                ?>
                <th></th>
                </thead>
                <?php
               $sql = "SELECT * FROM progman ORDER BY id;";
                $result = mysqli_query($conn, $sql);
                while ($row = mysqli_fetch_array($result, MYSQLI_ASSOC)) {
                    if (isset($_POST['edit']) and $_POST['edit'] == $row['id']) {
                        echo "<tr><td><button style='color: blue; background-color: #5cb85c; max-height: 20px; padding-top: 0' type='submit' name='edit' value='" . $row['id'] . "' class='btn btn-default' disabled>" . $row['id'] . "</button></td>";
                        echo "<td><input type='text' name='denumire' class='form-control' value='".$row['denumire']."'></td>";
                        echo "<td><input style='min-width: 15px' type='number' name='durata_t1' class='form-control' value='".$row['durata_t1']."'></td>";
                        echo "<td><input style='min-width: 15px' type='number' name='durata_t2' class='form-control' value='".$row['durata_t2']."'></td>";
                        echo "<td><input style='min-width: 30px' type='number' name='durata_t3' class='form-control' value='".$row['durata_t3']."'></td>";
                        echo "<td><input style='min-width: 15px' type='number' name='durata_t4' class='form-control' value='".$row['durata_t4']."'></td>";
                        //echo "<td><button style='max-height: 20px; padding-top: 0' type='submit' name='edex' value='\".$row['id'].\"' class='btn btn-success'>Confirma</button>\";
                        echo "<td><button style='max-height: 20px; padding-top: 0' type='submit' name='edex' class='btn btn-success' value='".$row['id']."'>Confirma</td></tr>";
                    } else {
                        echo "<tr><td><button style='color: blue; background-color: #5cb85c; max-height: 20px; padding-top: 0' type='submit' name='edit' value='" . $row['id'] . "' class='btn btn-default'>" . $row['id'] . "</button></td>";
                        echo "<td>" . $row['denumire'] . "</td>";
                        echo "<td style='horiz-align: right'>" . $row['durata_t1'] . "</td>";
                        echo "<td style='horiz-align: right'>" . $row['durata_t2'] . "</td>";
                        echo "<td style='horiz-align: right'>" . $row['durata_t3'] . "</td>";
                        echo "<td style='horiz-align: right'>" . $row['durata_t4'] . "</td>";
                        echo "<td><button style='max-height: 20px; padding-top: 0' type='submit' name='execute' value='" . $row['id'] . "' class='btn btn-danger'>Executa ACUM!</button></td>";
                    }
                }
                mysqli_free_result($result);
                ?>
            </table>
        </div>
    </form>
</div>

<?php
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
    echo "<script>window.location='mainpage.php'</script>";
}
if (isset($_POST['execute'])) {
    irigatie_controller_exec($ini_array, $_POST['execute']);
}
mysqli_close($conn);
