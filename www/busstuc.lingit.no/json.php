<?PHP;
$prog = "/usr/bin/ttpc --json";
$quest = $_POST["question"];

if ($quest)
  {
    # Tegn som skal fjærnes fra input.
    
    $removes = array("'", '"', '\\', '`', '´', '[', ']');

    # "Snillifiserer" input:
    #
    # - substr kutter all input som kommer etter tegn nummer 1024.
    # - strip_tags fjerner eventuelle HTML (eller XML)-tags.
    # - str_replace fjerner tegnene som ramses opp ovenfor.
    # - trim fjerner eventuelle white-space i starten og slutten av strengen.
    
    $e = trim(str_replace($removes, "", strip_tags(substr($quest, 0, 1024))));

    # Dersom strengen nå inneholder "ekle" tegn, vil vi ikke behandle den.
    
    if (! ereg("^[*a-zA-ZæøåÆØÅéÉöÖäÄ0-9,. ?!@:+-/]*$", $e))
      {
	unset($e);
      }
  }

if ($e)
  {
    # Dersom det mangler et '.' i slutten av setningen, legg det til.
    
    if ($e && (! ereg("[.?!]$", $e)))
      {
	$e = $e.".";
      }
    
    printf("<ul><li>%s</li>", $e);
    
    setlocale(LC_CTYPE, "UTF8", "nb_NO.UTF-8");
    $e = escapeshellarg($e);
    
    print "<li>";
    if ($_POST["tekniskinfo"])
      {
	printf("<pre>");
	system("$tech_prog $e 2>&1");
	printf("</pre>");
      }
    else
      {
	system("$prog $e");
      }
    
    print "</li></ul>";
  }
 else
   {
     print "Du må taste inn et spørsmål før du trykker på \"Send spørsmål\".";
   }
?>
