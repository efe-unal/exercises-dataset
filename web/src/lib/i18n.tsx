/**
 * Interface translation.
 *
 * The dataset already carries exercise instructions in nine languages; this
 * covers the words around them. No library: a flat dictionary keyed by a
 * dotted string is enough at this size, and a missing key falls back to
 * English rather than showing the reader a raw identifier.
 *
 * The language follows the signed-in account's preference, so it is the same
 * on every device, and falls back to the browser's before a user exists.
 */

import { createContext, useContext, useMemo, type ReactNode } from 'react';

import { useAuth } from './auth';

type Dictionary = Record<string, string>;

const en: Dictionary = {
  'app.name': 'Training',
  'nav.today': 'Today',
  'nav.programs': 'Programs',
  'nav.exercises': 'Exercises',
  'nav.progress': 'Progress',
  'nav.settings': 'Settings',

  'common.loading': 'Loading…',
  'common.working': 'Working…',
  'common.retry': 'Try again',
  'common.delete': 'Delete',
  'common.back': 'Go back',
  'common.notFound': 'Not found',
  'common.min': 'min',
  'common.week': 'Week',
  'common.saved': 'Saved.',

  'auth.signIn': 'Sign in',
  'auth.signUp': 'Sign up',
  'auth.createAccount': 'Create an account',
  'auth.createAccountButton': 'Create account',
  'auth.signOut': 'Sign out',
  'auth.email': 'Email',
  'auth.password': 'Password',
  'auth.nameOptional': 'Name (optional)',
  'auth.passwordHint': 'At least 8 characters.',
  'auth.haveAccount': 'Already have an account?',
  'auth.noAccount': 'No account yet?',
  'auth.createOne': 'Create one',

  'today.noProgramTitle': 'No active program',
  'today.noProgramBody':
    'Generate a block and save it, and it will show up here session by session.',
  'today.buildProgram': 'Build a program',
  'today.completeTitle': 'Block complete',
  'today.completeBody':
    'Every session in this block is logged. Generate the next one when you are ready.',
  'today.buildNext': 'Build the next block',
  'today.errorTitle': "Could not load today's session",
  'today.logged': 'logged',
  'today.deloadWeek': 'deload week',
  'today.finish': 'Finish session',
  'today.saving': 'Saving…',
  'today.needOneSet': 'Log at least one set before finishing.',
  'today.sessionSaved': 'Session saved.',
  'today.savedOffline':
    'No connection — the session is saved on this device and will sync automatically.',
  'today.rest': 'rest',

  'sets.kg': 'kg',
  'sets.reps': 'reps',
  'sets.addSet': 'Add set',
  'sets.warmup': 'Warmup',
  'sets.progress': '{done} of {total} working sets logged',

  'builder.title': 'Build a program',
  'builder.goalQuestion': 'What are you training for?',
  'builder.levelQuestion': 'How much training have you done?',
  'builder.equipmentQuestion': 'What do you have to train with?',
  'builder.daysPerWeek': 'Days per week',
  'builder.sessionMinutes': 'Minutes per session',
  'builder.blockLength': 'Block length',
  'builder.weeks': 'weeks',
  'builder.generate': 'Show me the program',
  'builder.save': 'Save and start this block',
  'builder.signUpPrompt':
    'Create an account to save this block and log your sessions',
  'builder.freeLimit':
    'Free accounts keep one program at a time. Delete the old one, or upgrade to keep several.',

  'goal.hypertrophy': 'Build muscle',
  'goal.strength': 'Get stronger',
  'goal.fat_loss': 'Lose fat',
  'goal.endurance': 'Muscular endurance',
  'goal.general_fitness': 'General fitness',

  'level.beginner': 'New to training',
  'level.beginner.hint': 'Under a year of consistent lifting',
  'level.intermediate': 'Experienced',
  'level.intermediate.hint': 'One to three years',
  'level.advanced': 'Advanced',
  'level.advanced.hint': 'Several years of structured training',

  'equipment.full_gym': 'Full gym',
  'equipment.home_dumbbell': 'Dumbbells at home',
  'equipment.home_minimal': 'Bands and a ball',
  'equipment.bodyweight': 'Bodyweight only',

  'programs.title': 'Your programs',
  'programs.new': 'New program',
  'programs.empty': 'Nothing saved yet. Build a block and it will appear here.',
  'programs.active': 'Active',
  'programs.makeActive': 'Make active',
  'programs.confirmDelete':
    'Delete this program and everything logged against it?',
  'programs.daysPerWeek': 'days/week',

  'exercises.title': 'Exercises',
  'exercises.search': 'Search by name…',
  'exercises.anyBodyPart': 'Any body part',
  'exercises.anyEquipment': 'Any equipment',
  'exercises.anyDifficulty': 'Any difficulty',
  'exercises.searching': 'Searching…',
  'exercises.count': '{count} exercises',
  'exercises.previous': 'Previous',
  'exercises.next': 'Next',
  'exercises.howTo': 'How to do it',
  'exercises.yourHistory': 'Your history',
  'exercises.noHistory':
    'Nothing logged yet. Once you train this movement, your progress shows up here.',
  'exercises.nextLoad': 'Next',
  'exercises.bodyweight': 'bodyweight',

  'progress.title': 'Progress',
  'progress.sessions': 'Sessions',
  'progress.workingSets': 'Working sets',
  'progress.totalVolume': 'Total volume',
  'progress.lastSession': 'Last session',
  'progress.recent': 'Recent sessions',
  'progress.nothingLogged': 'Nothing logged yet.',
  'progress.sets': 'sets',

  'chart.needMore':
    'Two or more logged sessions are needed before a trend is worth drawing.',
  'chart.caption':
    'Estimated one-rep max — load and reps folded into one comparable number.',
  'chart.viewTable': 'View as table',
  'chart.hideTable': 'Hide table',
  'chart.date': 'Date',
  'chart.estimated1rm': 'Estimated 1RM (kg)',
  'chart.estimatedShort': 'estimated',

  'settings.title': 'Settings',
  'settings.signedInAs': 'Signed in as',
  'settings.language': 'Instruction language',
  'settings.units': 'Units',
  'settings.metric': 'Metric (kg)',
  'settings.imperial': 'Imperial (lb)',

  'offline.offline': 'Offline — your sets are saved on this device.',
  'offline.pending': '{count} session(s) waiting to sync.',

  'plan.weeklyVolume': 'Weekly sets per body part',
  'plan.progression': 'progression',
  'plan.deloadWeek': 'Deload week.',

  // Day names and slot labels the API sends as keys alongside English text.
  'day.full_body_a': 'Full body A',
  'day.full_body_b': 'Full body B',
  'day.full_body_c': 'Full body C',
  'day.upper_body': 'Upper body',
  'day.lower_body': 'Lower body',
  'day.push': 'Push',
  'day.pull': 'Pull',
  'day.legs': 'Legs',

  'slot.squat_pattern': 'Squat',
  'slot.hip_hinge': 'Hip hinge',
  'slot.horizontal_push': 'Horizontal push',
  'slot.horizontal_pull': 'Horizontal pull',
  'slot.vertical_push': 'Vertical push',
  'slot.vertical_pull': 'Vertical pull',
  'slot.single_leg': 'Single leg',
  'slot.posterior_chain': 'Posterior chain',
  'slot.shoulder_isolation': 'Shoulders',
  'slot.elbow_flexion': 'Biceps',
  'slot.elbow_extension': 'Triceps',
  'slot.chest_accessory': 'Chest accessory',
  'slot.back_accessory': 'Back accessory',
  'slot.quad_accessory': 'Quad accessory',
  'slot.rear_delts_traps': 'Rear delts / traps',
  'slot.grip_forearms': 'Grip and forearms',
  'slot.calves': 'Calves',
  'slot.core': 'Core',
  'slot.arms': 'Arms',

  'guidance.linear_load':
    'Add the smallest load step whenever every set hits the top of the rep range.',
  'guidance.double':
    'Work the reps up to the top of the range at the same load, then add one load step and start again at the bottom.',
  'guidance.volume_wave':
    'Volume rises each week and so does the effort, up to the deload.',
  'guidance.deload': 'Deload — cut the volume, keep the movements.',

  'suggestion.establish':
    'No history yet. Work up to a weight you could stop {margin} reps short of failure, and treat that as your starting load.',
  'suggestion.add_load':
    'Every set reached {repMax}. Add {step} kg and start again at {repMin} reps.',
  'suggestion.repeat':
    'Stay at this load and add reps until every set reaches {repMax}.',
  'suggestion.deload':
    'This load has stalled for two sessions. Drop to {weight} kg and build back up.',
  'suggestion.bodyweight':
    'Bodyweight movement — add reps, then move to a harder variation.',
};

const tr: Dictionary = {
  'app.name': 'Antrenman',
  'nav.today': 'Bugün',
  'nav.programs': 'Programlar',
  'nav.exercises': 'Egzersizler',
  'nav.progress': 'İlerleme',
  'nav.settings': 'Ayarlar',

  'common.loading': 'Yükleniyor…',
  'common.working': 'İşleniyor…',
  'common.retry': 'Tekrar dene',
  'common.delete': 'Sil',
  'common.back': 'Geri dön',
  'common.notFound': 'Bulunamadı',
  'common.min': 'dk',
  'common.week': 'Hafta',
  'common.saved': 'Kaydedildi.',

  'auth.signIn': 'Giriş yap',
  'auth.signUp': 'Kayıt ol',
  'auth.createAccount': 'Hesap oluştur',
  'auth.createAccountButton': 'Hesap oluştur',
  'auth.signOut': 'Çıkış yap',
  'auth.email': 'E-posta',
  'auth.password': 'Şifre',
  'auth.nameOptional': 'İsim (isteğe bağlı)',
  'auth.passwordHint': 'En az 8 karakter.',
  'auth.haveAccount': 'Zaten hesabın var mı?',
  'auth.noAccount': 'Henüz hesabın yok mu?',
  'auth.createOne': 'Hemen oluştur',

  'today.noProgramTitle': 'Aktif program yok',
  'today.noProgramBody':
    'Bir program oluşturup kaydet, burada seans seans karşına gelsin.',
  'today.buildProgram': 'Program oluştur',
  'today.completeTitle': 'Program tamamlandı',
  'today.completeBody':
    'Bu programdaki bütün seanslar kaydedildi. Hazır olduğunda yenisini oluştur.',
  'today.buildNext': 'Yeni program oluştur',
  'today.errorTitle': 'Bugünkü seans yüklenemedi',
  'today.logged': 'kaydedildi',
  'today.deloadWeek': 'hafifletme haftası',
  'today.finish': 'Seansı bitir',
  'today.saving': 'Kaydediliyor…',
  'today.needOneSet': 'Bitirmeden önce en az bir set kaydet.',
  'today.sessionSaved': 'Seans kaydedildi.',
  'today.savedOffline':
    'Bağlantı yok — seans bu cihaza kaydedildi, bağlantı gelince kendiliğinden gönderilecek.',
  'today.rest': 'dinlenme',

  'sets.kg': 'kg',
  'sets.reps': 'tekrar',
  'sets.addSet': 'Set ekle',
  'sets.warmup': 'Isınma',
  'sets.progress': '{total} setin {done} tanesi kaydedildi',

  'builder.title': 'Program oluştur',
  'builder.goalQuestion': 'Neyi hedefliyorsun?',
  'builder.levelQuestion': 'Ne kadar antrenman geçmişin var?',
  'builder.equipmentQuestion': 'Neyle çalışabiliyorsun?',
  'builder.daysPerWeek': 'Haftada gün sayısı',
  'builder.sessionMinutes': 'Seans süresi (dakika)',
  'builder.blockLength': 'Program uzunluğu',
  'builder.weeks': 'hafta',
  'builder.generate': 'Programı göster',
  'builder.save': 'Kaydet ve başla',
  'builder.signUpPrompt':
    'Bu programı kaydetmek ve antrenmanlarını işlemek için hesap oluştur',
  'builder.freeLimit':
    'Ücretsiz hesaplar tek program tutabilir. Eskisini sil ya da daha fazlası için yükselt.',

  'goal.hypertrophy': 'Kas yapmak',
  'goal.strength': 'Güçlenmek',
  'goal.fat_loss': 'Yağ yakmak',
  'goal.endurance': 'Kas dayanıklılığı',
  'goal.general_fitness': 'Genel kondisyon',

  'level.beginner': 'Yeni başlıyorum',
  'level.beginner.hint': 'Bir yıldan az düzenli antrenman',
  'level.intermediate': 'Deneyimliyim',
  'level.intermediate.hint': 'Bir ila üç yıl',
  'level.advanced': 'İleri seviye',
  'level.advanced.hint': 'Birkaç yıllık planlı antrenman',

  'equipment.full_gym': 'Tam donanımlı salon',
  'equipment.home_dumbbell': 'Evde dambıl',
  'equipment.home_minimal': 'Lastik ve top',
  'equipment.bodyweight': 'Sadece vücut ağırlığı',

  'programs.title': 'Programların',
  'programs.new': 'Yeni program',
  'programs.empty':
    'Henüz kayıt yok. Bir program oluştur, burada görünsün.',
  'programs.active': 'Aktif',
  'programs.makeActive': 'Aktif yap',
  'programs.confirmDelete':
    'Bu program ve ona işlenen bütün antrenmanlar silinsin mi?',
  'programs.daysPerWeek': 'gün/hafta',

  'exercises.title': 'Egzersizler',
  'exercises.search': 'İsimle ara…',
  'exercises.anyBodyPart': 'Tüm bölgeler',
  'exercises.anyEquipment': 'Tüm ekipmanlar',
  'exercises.anyDifficulty': 'Tüm zorluklar',
  'exercises.searching': 'Aranıyor…',
  'exercises.count': '{count} egzersiz',
  'exercises.previous': 'Önceki',
  'exercises.next': 'Sonraki',
  'exercises.howTo': 'Nasıl yapılır',
  'exercises.yourHistory': 'Geçmişin',
  'exercises.noHistory':
    'Henüz kayıt yok. Bu hareketi çalıştığında ilerlemen burada görünecek.',
  'exercises.nextLoad': 'Sıradaki',
  'exercises.bodyweight': 'vücut ağırlığı',

  'progress.title': 'İlerleme',
  'progress.sessions': 'Seans',
  'progress.workingSets': 'Çalışma seti',
  'progress.totalVolume': 'Toplam hacim',
  'progress.lastSession': 'Son seans',
  'progress.recent': 'Son seanslar',
  'progress.nothingLogged': 'Henüz kayıt yok.',
  'progress.sets': 'set',

  'chart.needMore':
    'Bir eğilim çizebilmek için en az iki kayıtlı seans gerekiyor.',
  'chart.caption':
    'Tahmini tek tekrar maksimumu — ağırlık ve tekrar tek bir karşılaştırılabilir sayıda.',
  'chart.viewTable': 'Tablo olarak gör',
  'chart.hideTable': 'Tabloyu gizle',
  'chart.date': 'Tarih',
  'chart.estimated1rm': 'Tahmini 1TM (kg)',
  'chart.estimatedShort': 'tahmini',

  'settings.title': 'Ayarlar',
  'settings.signedInAs': 'Giriş yapılan hesap',
  'settings.language': 'Anlatım dili',
  'settings.units': 'Birimler',
  'settings.metric': 'Metrik (kg)',
  'settings.imperial': 'İngiliz (lb)',

  'offline.offline': 'Çevrimdışı — setlerin bu cihaza kaydediliyor.',
  'offline.pending': 'Gönderilmeyi bekleyen {count} seans var.',

  'plan.weeklyVolume': 'Bölgeye göre haftalık set',
  'plan.progression': 'ilerleme',
  'plan.deloadWeek': 'Hafifletme haftası.',

  'day.full_body_a': 'Tüm vücut A',
  'day.full_body_b': 'Tüm vücut B',
  'day.full_body_c': 'Tüm vücut C',
  'day.upper_body': 'Üst vücut',
  'day.lower_body': 'Alt vücut',
  'day.push': 'İtme',
  'day.pull': 'Çekme',
  'day.legs': 'Bacak',

  'slot.squat_pattern': 'Squat',
  'slot.hip_hinge': 'Kalça menteşesi',
  'slot.horizontal_push': 'Yatay itme',
  'slot.horizontal_pull': 'Yatay çekme',
  'slot.vertical_push': 'Dikey itme',
  'slot.vertical_pull': 'Dikey çekme',
  'slot.single_leg': 'Tek bacak',
  'slot.posterior_chain': 'Arka zincir',
  'slot.shoulder_isolation': 'Omuz',
  'slot.elbow_flexion': 'Biceps',
  'slot.elbow_extension': 'Triceps',
  'slot.chest_accessory': 'Göğüs yardımcı',
  'slot.back_accessory': 'Sırt yardımcı',
  'slot.quad_accessory': 'Ön bacak yardımcı',
  'slot.rear_delts_traps': 'Arka omuz / trapez',
  'slot.grip_forearms': 'Kavrama ve ön kol',
  'slot.calves': 'Baldır',
  'slot.core': 'Karın ve gövde',
  'slot.arms': 'Kollar',

  'guidance.linear_load':
    'Her sette tekrar aralığının üst sınırına ulaştığında en küçük ağırlık artışını ekle.',
  'guidance.double':
    'Aynı ağırlıkta tekrarları üst sınıra çıkar, sonra bir kademe ağırlık ekleyip alt sınırdan başla.',
  'guidance.volume_wave':
    'Hacim her hafta artıyor, hafifletme haftasına kadar zorluk da yükseliyor.',
  'guidance.deload': 'Hafifletme — hacmi düşür, hareketleri koru.',

  'suggestion.establish':
    'Henüz kayıt yok. Tükenmeye {margin} tekrar kala bırakabileceğin bir ağırlığa çık ve onu başlangıç yükü say.',
  'suggestion.add_load':
    'Bütün setlerde {repMax} tekrara ulaştın. {step} kg ekle ve {repMin} tekrardan başla.',
  'suggestion.repeat':
    'Ağırlığı koru; her set {repMax} tekrara ulaşana kadar tekrar ekle.',
  'suggestion.deload':
    'Bu ağırlıkta iki seans takıldın. {weight} kg\'a düş ve yeniden çık.',
  'suggestion.bodyweight':
    'Vücut ağırlığı hareketi — tekrar ekle, sonra daha zor bir varyasyona geç.',
};

const DICTIONARIES: Record<string, Dictionary> = { en, tr };

/** Languages the interface itself is translated into. */
export const UI_LANGUAGES = Object.keys(DICTIONARIES);

export type Translate = (key: string, values?: Record<string, string | number>) => string;

const I18nContext = createContext<{ t: Translate; language: string } | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  const language = useMemo(() => {
    if (user?.language && DICTIONARIES[user.language]) return user.language;
    const browser = globalThis.navigator?.language?.slice(0, 2);
    return browser && DICTIONARIES[browser] ? browser : 'en';
  }, [user?.language]);

  const value = useMemo(() => {
    const dictionary = DICTIONARIES[language] ?? en;
    const t: Translate = (key, values) => {
      // English is the source of truth, so an untranslated key still reads as
      // a sentence rather than as `today.finish`.
      const template = dictionary[key] ?? en[key] ?? key;
      if (!values) return template;
      return template.replace(/\{(\w+)\}/g, (match, name: string) =>
        name in values ? String(values[name]) : match,
      );
    };
    return { t, language };
  }, [language]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/**
 * Translate a server-supplied label by its key, falling back to the English
 * text the API already sent.
 *
 * Plans are stored snapshots, so an old one may carry no key at all; the
 * fallback is what keeps those readable instead of blank.
 */
export function labelFor(t: Translate, prefix: string, key: string,
                         fallback: string): string {
  if (!key) return fallback;
  const translated = t(`${prefix}.${key}`);
  return translated === `${prefix}.${key}` ? fallback : translated;
}

export function useTranslation() {
  const context = useContext(I18nContext);
  if (context === null) {
    throw new Error('useTranslation must be used inside an I18nProvider');
  }
  return context;
}
