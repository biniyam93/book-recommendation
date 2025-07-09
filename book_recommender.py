from hyperon import MeTTa
import google.generativeai as genai
from typing import List, Tuple, Optional

class BookRecommender:
    def __init__(self):
        print("\n[DEBUG] Initializing BookRecommender...")
        self.metta = MeTTa()
        self._init_knowledge_base()

        genai.configure(api_key='AIzaSyB4_TlmuGtvoBVbcNJjYfEGupyLL7q0HIU')  # replace with your key
        self.llm = genai.GenerativeModel('gemini-2.5-flash')
        print("[DEBUG] Gemini model configured.")

    def _init_knowledge_base(self):
        print("\n[DEBUG] Initializing MeTTa knowledge base...")
        self.metta.run('''
            ;; Authors
            (Author (Agatha Christie))
            (Author (Terry Pratchett))
            (Author (Neil Gaiman))
            (Author (Isaac Asimov))

            ;; Books
            (Book (
                (title (Murder on the Orient Express))
                (authors ((Agatha Christie)))
                (genre ((Mystery)))
                (year 1934)
                (description (A murder occurs on a luxury train...))
                (related ((Death on the Nile)))
            ))

            (Book (
                (title (Death on the Nile))
                (authors ((Agatha Christie)))
                (genre ((Mystery)))
                (year 1937)
                (description (Poirot solves a murder during a Nile cruise...))
                (related ((Murder on the Orient Express)))
            ))

            (Book (
                (title (Good Omens))
                (authors ((Terry Pratchett) (Neil Gaiman)))
                (genre ((Fantasy) (Comedy)))
                (year 1990)
                (description (An angel and demon try to prevent the apocalypse...))
                (related ())
            ))
            (Book (
                (title (Small Gods))
                (authors ((Terry Pratchett)))
                (genre ((Fantasy) (Satire)))
                (year 1992)
                (description (A god struggles to regain followers in a philosophical fantasy.))
                (related ())
            ))
                       
        ''')
        print("[DEBUG] Knowledge base initialized.")

    def _atom_to_str(self, atom):
        return atom.get_name() if hasattr(atom, 'get_name') else str(atom)

    def _understand_query(self, query: str) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        print("\n[DEBUG] Understanding user query with Gemini...")
        prompt = f"""
        Analyze this book query and extract the relevant preferences:
        "{query}"

        Return ONLY in this format:
        authors:<comma_separated_authors_or_none>
        genres:<comma_separated_genres_or_none>
        """
        response = self.llm.generate_content(prompt)
        print("[DEBUG] Gemini raw response:")
        print(response.text)

        authors, genres = None, None
        lines = response.text.strip().split('\n')
        for line in lines:
            if line.startswith('authors:'):
                authors_str = line.replace('authors:', '').strip()
                if authors_str.lower() != 'none':
                    authors = [a.strip() for a in authors_str.split(',')]
            elif line.startswith('genres:'):
                genres_str = line.replace('genres:', '').strip()
                if genres_str.lower() != 'none':
                    genres = [g.strip() for g in genres_str.split(',')]

        print("[DEBUG] Parsed authors:", authors)
        print("[DEBUG] Parsed genres:", genres)
        return authors, genres

    def _get_recommendations(self, authors: Optional[List[str]] = None,
                             genres: Optional[List[str]] = None) -> List[Tuple]:
        print("\n[DEBUG] Building MeTTa query for recommendations...")

        base_query = '''
        !(match &self 
            (Book (
                (title $title)
                (authors $a)
                (genre $g)
                (year $y)
                (description $d)
                (related $r)
            ))
            ($title $a $g $y $d $r)
        )
        '''

        query = base_query

        if authors:
            authors = [a.title() for a in authors]
            authors_list = " ".join(f"({a})" for a in authors)
            query = query.replace('(authors $a)', '(authors $a)')
            query = query.replace('$a', f'({authors_list})')

        if genres:
            genres = [g.title() for g in genres]
            genres_list = " ".join(f"({g})" for g in genres)
            query = query.replace('(genre $g)', '(genre $g)')
            query = query.replace('$g', f'({genres_list})')

        print("[DEBUG] Final MeTTa query:\n", query)

        result = self.metta.run(query)
        print("[DEBUG] Raw MeTTa result:", result)

        recommendations = []
        if result:
            for item in result:
                if isinstance(item, list):
                    for sub in item:
                        if isinstance(sub, tuple) and len(sub) == 6:
                            recommendations.append(sub)
                        elif hasattr(sub, 'get_children'):
                            children = sub.get_children()
                            if len(children) == 6:
                                recommendations.append(tuple(children))

        print("[DEBUG] Initial recommendations found:", len(recommendations))

        # ---- Related books ----
        related_books = []
        for rec in recommendations:
            title, authors_raw, genre, year, desc, related = rec
            if related:
                if hasattr(related, 'get_children'):
                    related_items = related.get_children()
                else:
                    related_items = [related]

                related_titles = " ".join(f'({self._atom_to_str(r)})' for r in related_items)
                related_query = f'''
                !(match &self 
                    (Book (
                        (title $t)
                        (authors $a)
                        (genre $g)
                        (year $y)
                        (description $d)
                        (related {related_titles})
                    ))
                    ($t $a $g $y $d {related_titles})
                )
                '''
                print("[DEBUG] Related book query:\n", related_query)
                related_result = self.metta.run(related_query)
                print("[DEBUG] Related result:", related_result)

                if related_result:
                    for item in related_result:
                        if isinstance(item, list):
                            for sub in item:
                                if isinstance(sub, tuple) and len(sub) == 6:
                                    related_books.append(sub)
                                elif hasattr(sub, 'get_children'):
                                    children = sub.get_children()
                                    if len(children) == 6:
                                        related_books.append(tuple(children))

        print("[DEBUG] Related books found:", len(related_books))

        # ---- Combine and deduplicate ----
        combined = recommendations + related_books
        unique_books = []
        seen_keys = set()

        for rec in combined:
            title_str = self._atom_to_str(rec[0]).strip('()').strip()
            year_str = str(rec[3])
            key = f"{title_str}_{year_str}"
            if key not in seen_keys:
                unique_books.append(rec)
                seen_keys.add(key)

        print("[DEBUG] Total unique recommendations:", len(unique_books))
        return unique_books

    def _generate_response(self, user_query: str, books: List[Tuple]) -> str:
        print("\n[DEBUG] Generating final response with Gemini...")

        if not books:
            print("[DEBUG] No matches found. Suggesting fallback.")
            return self.llm.generate_content(
                f"The user asked: '{user_query}'\n"
                "No matching books found in the knowledge base. Suggest 2-3 alternatives."
            ).text

        books_formatted = []
        for book in books[:5]:
            title, authors_raw, genre, year, desc, _ = book
            authors = [self._atom_to_str(a) for a in authors_raw] if hasattr(authors_raw, '__iter__') else [self._atom_to_str(authors_raw)]
            authors_str = " & ".join(authors)
            genre_str = " & ".join([self._atom_to_str(g) for g in genre]) if hasattr(genre, '__iter__') else self._atom_to_str(genre)
            books_formatted.append(f"- {title} by {authors_str} ({year}, {genre_str}): {desc}")

        books_str = "\n".join(books_formatted)
        prompt = (
            f"User query: '{user_query}'\n\n"
            "These books were found in our knowledge base:\n"
            f"{books_str}\n\n"
            "Write a friendly, helpful response under 200 words ONLY using these books — do not add any external suggestions."
        )

        response = self.llm.generate_content(prompt)
        print("[DEBUG] Final Gemini response generated.")
        return response.text

    def recommend(self, user_query: str) -> str:
        print("\n[DEBUG] Running full recommendation pipeline...")
        authors, genres = self._understand_query(user_query)
        books = self._get_recommendations(authors, genres)
        return self._generate_response(user_query, books)


if __name__ == "__main__":
    recommender = BookRecommender()

    test_queries = [
        "I love Agatha Christie's mystery novels. What should I read next?"
    ]

    for query in test_queries:
        print("\n=============================================")
        print("User Query:", query)
        print("Recommendation:\n", recommender.recommend(query))
        print("=============================================")
