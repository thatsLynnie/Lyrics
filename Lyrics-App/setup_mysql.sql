CREATE DATABASE IF NOT EXISTS lyrics
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

DROP USER IF EXISTS 'lyrics_app'@'127.0.0.1';
DROP USER IF EXISTS 'lyrics_app'@'localhost';

SET @lyrics_app_password = LEFT(
  SHA2(CONCAT(UUID(), UUID(), RAND(), CURRENT_TIMESTAMP(6)), 256),
  48
);
SET @create_lyrics_app_user = CONCAT(
  "CREATE USER 'lyrics_app'@'127.0.0.1' IDENTIFIED BY '",
  @lyrics_app_password,
  "'"
);
PREPARE create_lyrics_app_user FROM @create_lyrics_app_user;
EXECUTE create_lyrics_app_user;
DEALLOCATE PREPARE create_lyrics_app_user;

SET @create_lyrics_app_local_user = CONCAT(
  "CREATE USER 'lyrics_app'@'localhost' IDENTIFIED BY '",
  @lyrics_app_password,
  "'"
);
PREPARE create_lyrics_app_local_user FROM @create_lyrics_app_local_user;
EXECUTE create_lyrics_app_local_user;
DEALLOCATE PREPARE create_lyrics_app_local_user;

GRANT ALL PRIVILEGES ON lyrics.* TO 'lyrics_app'@'127.0.0.1';
GRANT ALL PRIVILEGES ON lyrics.* TO 'lyrics_app'@'localhost';

SELECT
  @lyrics_app_password AS lyrics_mysql_password,
  CHAR_LENGTH(@lyrics_app_password) AS password_length;
