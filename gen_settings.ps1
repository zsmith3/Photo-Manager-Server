$chars = @("a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "!", "@", "#", "$", "%", "^", "&", "*", "(", "-", "_", "=", "+", ")")
$secret = ""
for ($i = 0; $i -lt 50; $i++) {
    $secret += Get-Random $chars
}

Set-Content "./photo_manager/settings/user.py" "SECRET_KEY = `"$secret`"`n`n# Add your custom settings here (using standard django setting names)"
