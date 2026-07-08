<?php
include('header.php');
$conn = mysqli_connect($ini_array['DB_SERVER'], $ini_array['DB_USER'], $ini_array['DB_PASS'],$ini_array['DB_NAME']);
if (mysqli_connect_errno()) {
    die("<pre style='color:#EE2711'>Failed to connect to MySQL: {".mysql_connect_error()."}</pre>");
}
?>
<div class="container" id="tables" style="margin-left: 20px">
    <form action="trasee.php" method="post" id="myForm" onsubmit="window.location.reload()">
        <div class="form-group row">
            <table class="table table-hover" id="myTable" style="white-space: nowrap">
                <thead>
                <th></th>
                <th>DENUMIRE</th>
                <th>TIP</th>
                <th>ACTIV</th>
                <th></th>
                </thead>
                <?php
                $sql = "SELECT * FROM trasee;";
                $result = mysqli_query($conn, $sql);
                while ($row = mysqli_fetch_array($result, MYSQLI_ASSOC)) {
                    if (isset($_POST['edit']) && ($_POST['edit'] == $row['id'])) {
                        echo "<tr>";
                        echo "<td><button style='color: blue; background-color: #5cb85c; max-height: 20px; padding-top: 0' type='submit' name='edit' value='" . $row['id'] . "' class='btn btn-default' disabled>" . $row['id'] . "</button></td>";
                        echo "<td><input type='text' name='denumire' class='form-control' value='".$row['denumire']."'></td>";
                        echo "<td><select name='tip' class='form-control'>";
                        if ($row['tip'] == 2) {
                            echo "<option value='1'>Aspersor</option>";
                            echo "<option value='2' selected>Picurator</option>";
                        } else {
                            echo "<option value='1' selected>Aspersor</option>";
                            echo "<option value='2'>Picurator</option>";
                        }
                        echo "</select></td>";
                        echo "<td>";
                        if ($row['activ']) {
                            echo "<input type='checkbox' name='activ' class='form-check-input' value='1' checked>";
                        } else {
                            echo "<input type='checkbox' name='activ' class='form-check-input' value='0'>";
                        }
                        echo "<td><button style='max-height: 20px; padding-top: 0' type='submit' name='edex' class='btn btn-success' value='".$row['id']."'>Confirma</td></tr>";
                    } else {
                        echo "<tr>";
                        echo "<td><button style='color: blue; background-color: #5cb85c; max-height: 20px; padding-top: 0' type='submit' name='edit' value='" . $row['id'] . "' class='btn btn-default'>" . $row['id'] . "</button></td>";
                        echo "<td>" . $row['denumire'] . "</td>";
                        if ($row['tip'] == 1) {
                            echo "<td>Aspersor</td>";
                        } elseif ($row['tip'] == 2) {
                            echo "<td>Picurator</td>";
                        } else {
                            echo "<td>Necunoscut</td>";
                        }
                        if ($row['activ']) {
                            echo "<td><input type='checkbox' class='form-check-input' checked disabled></td>";
                        } else {
                            echo "<td><input type='checkbox' class='form-check-input' disabled></td>";
                        }
                        echo "</tr>";
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
    if (isset($_POST['activ'])) {
        $activ = 1;
    } else {
        $activ = 0;
    }
    $stmt = mysqli_prepare($conn, "UPDATE trasee SET denumire = ?, tip = ?, activ = ? WHERE id = ?;");
    if (!$stmt) {
        die ("<pre style='color:#EE2711'>Failed to connect to MySQL: {".mysqli_error($conn)."}</pre>");
    }
    mysqli_stmt_bind_param($stmt, "siii", $_POST['denumire'], $_POST['tip'], $activ, $_POST['edex']);
    mysqli_stmt_execute($stmt);
    mysqli_stmt_close($stmt);
    unset($_POST);
    echo "<script>window.location='mainpage.php'</script>";
}
mysqli_close($conn);
